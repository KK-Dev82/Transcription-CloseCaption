/**
 * Live Streaming Tab - Close Caption
 * Record 3 seconds of audio from HLS stream and generate Close Caption
 */

// Global state
let liveStreamingState = {
    videoElement: null,
    hlsPlayer: null,
    isRecording: false,
    recordingStartTime: null,
    mediaRecorder: null,
    audioChunks: [],
    audioContext: null,
    audioSource: null,
    currentTaskId: null,
    recentCaptions: [],
    serverName: '4000-ada-sc'
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const videoElement = document.getElementById('liveStreamVideo');
    if (videoElement) {
        liveStreamingState.videoElement = videoElement;
        initializeHLSPlayer();
    }
    
    // Listen for webhook events
    window.addEventListener('webhook:task-update', handleWebhookUpdate);
});

/**
 * Initialize HLS Player
 */
function initializeHLSPlayer() {
    const hlsUrl = document.getElementById('hlsUrl').value;
    const videoElement = liveStreamingState.videoElement;
    
    if (!hlsUrl || !videoElement) {
        return;
    }
    
    // Extract channel name from HLS URL
    // Format: http://143.198.77.135:80/hls/channel1.m3u8
    let channel = 'channel1';
    const channelMatch = hlsUrl.match(/\/([^\/]+)\.m3u8/);
    if (channelMatch) {
        channel = channelMatch[1];
    }
    
    // Use proxy endpoint to avoid Mixed Content issues
    // Dashboard (HTTPS) -> Proxy (HTTPS) -> HLS Server (HTTP)
    const proxyUrl = `/api/live-streaming/hls-proxy/${channel}`;
    
    // Check if HLS.js is available
    if (typeof Hls !== 'undefined') {
        if (liveStreamingState.hlsPlayer) {
            liveStreamingState.hlsPlayer.destroy();
        }
        
        const hls = new Hls({
            enableWorker: true,
            lowLatencyMode: true,
            backBufferLength: 90,
            xhrSetup: function(xhr, url) {
                // Ensure all requests go through proxy
                if (url.includes('.m3u8') || url.includes('.ts')) {
                    // URL is already proxied, no need to modify
                }
            }
        });
        
        // Use proxy URL instead of direct HLS URL
        hls.loadSource(proxyUrl);
        hls.attachMedia(videoElement);
        
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
            console.log('✅ HLS manifest parsed (via proxy)');
            updateStreamStatus('✅ Stream loaded - Click play to start');
            // Don't auto-play - let user click play button (browser security requirement)
        });
        
        hls.on(Hls.Events.ERROR, (event, data) => {
            console.error('HLS error:', data);
            if (data.fatal) {
                if (data.type === 'networkError') {
                    updateStreamStatus('❌ Network error - Check HLS URL and server');
                } else {
                    updateStreamStatus('❌ Stream error: ' + (data.type || 'Unknown'));
                }
                
                // Try to recover
                if (data.type === 'networkError' && data.fatal) {
                    console.log('Attempting to recover from network error...');
                    setTimeout(() => {
                        if (liveStreamingState.hlsPlayer) {
                            liveStreamingState.hlsPlayer.startLoad();
                        }
                    }, 1000);
                }
            }
        });
        
        liveStreamingState.hlsPlayer = hls;
    } else if (videoElement.canPlayType('application/vnd.apple.mpegurl')) {
        // Native HLS support (Safari) - use proxy URL
        videoElement.src = proxyUrl;
        videoElement.addEventListener('loadedmetadata', () => {
            updateStreamStatus('✅ Stream loaded');
        });
    } else {
        updateStreamStatus('❌ HLS.js not loaded - please include HLS.js library');
    }
}

/**
 * Update stream status
 */
function updateStreamStatus(message) {
    const statusEl = document.getElementById('streamStatus');
    if (statusEl) {
        statusEl.textContent = message;
    }
}

/**
 * Start recording 3 seconds of audio from video stream
 */
async function startRecording() {
    if (liveStreamingState.isRecording) {
        return;
    }
    
    const videoElement = liveStreamingState.videoElement;
    if (!videoElement || videoElement.readyState < 2) {
        alert('⚠️ Please wait for stream to load first');
        return;
    }
    
    try {
        // Capture audio from video element using Web Audio API
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaElementSource(videoElement);
        const destination = audioContext.createMediaStreamDestination();
        
        // Connect source to destination
        source.connect(destination);
        source.connect(audioContext.destination); // Also connect to speakers
        
        // Create MediaRecorder from captured stream
        const stream = destination.stream;
        const mediaRecorder = new MediaRecorder(stream, {
            mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg'
        });
        
        liveStreamingState.mediaRecorder = mediaRecorder;
        liveStreamingState.audioChunks = [];
        liveStreamingState.isRecording = true;
        liveStreamingState.recordingStartTime = Date.now();
        liveStreamingState.audioContext = audioContext;
        liveStreamingState.audioSource = source;
        
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                liveStreamingState.audioChunks.push(event.data);
            }
        };
        
        mediaRecorder.onstop = async () => {
            // Create blob from chunks
            const audioBlob = new Blob(liveStreamingState.audioChunks, { 
                type: mediaRecorder.mimeType || 'audio/webm' 
            });
            
            // Cleanup audio context
            if (liveStreamingState.audioSource) {
                liveStreamingState.audioSource.disconnect();
            }
            if (liveStreamingState.audioContext) {
                await liveStreamingState.audioContext.close();
            }
            
            // Send to transcription service
            await sendAudioForCloseCaption(audioBlob);
            
            // Reset state
            liveStreamingState.isRecording = false;
            liveStreamingState.audioChunks = [];
            liveStreamingState.audioContext = null;
            liveStreamingState.audioSource = null;
            updateRecordButton();
        };
        
        // Start recording
        mediaRecorder.start();
        updateRecordButton();
        updateRecordStatus('🔴 Recording... (3 seconds)');
        
        // Stop after 3 seconds
        setTimeout(() => {
            if (liveStreamingState.isRecording && liveStreamingState.mediaRecorder && liveStreamingState.mediaRecorder.state !== 'inactive') {
                liveStreamingState.mediaRecorder.stop();
            }
        }, 3000);
        
    } catch (error) {
        console.error('Error starting recording:', error);
        alert('❌ Error starting recording: ' + error.message + '\n\nNote: Browser may require user interaction first. Try clicking play on the video first.');
        liveStreamingState.isRecording = false;
        updateRecordButton();
        
        // Cleanup on error
        if (liveStreamingState.audioContext) {
            try {
                liveStreamingState.audioContext.close();
            } catch (e) {
                // Ignore cleanup errors
            }
        }
    }
}

/**
 * Stop recording manually
 */
function stopRecording() {
    if (liveStreamingState.mediaRecorder && liveStreamingState.mediaRecorder.state !== 'inactive') {
        liveStreamingState.mediaRecorder.stop();
    }
    
    // Cleanup audio context
    if (liveStreamingState.audioSource) {
        try {
            liveStreamingState.audioSource.disconnect();
        } catch (e) {
            // Ignore cleanup errors
        }
    }
    if (liveStreamingState.audioContext) {
        liveStreamingState.audioContext.close().catch(e => {
            // Ignore cleanup errors
        });
    }
}

/**
 * Update record button state
 */
function updateRecordButton() {
    const recordBtn = document.getElementById('recordButton');
    const stopBtn = document.getElementById('stopRecordButton');
    
    if (liveStreamingState.isRecording) {
        recordBtn.style.display = 'none';
        stopBtn.style.display = 'inline-block';
    } else {
        recordBtn.style.display = 'inline-block';
        stopBtn.style.display = 'none';
    }
}

/**
 * Update record status
 */
function updateRecordStatus(message) {
    const statusEl = document.getElementById('recordStatus');
    if (statusEl) {
        statusEl.textContent = message;
    }
}

/**
 * Send audio to transcription service for Close Caption
 */
async function sendAudioForCloseCaption(audioBlob) {
    try {
        updateRecordStatus('📤 Uploading audio...');
        updateCaptionStatus('Status: Uploading audio...');
        
        // Get server config
        const serverName = document.getElementById('liveStreamingServer').value;
        liveStreamingState.serverName = serverName;
        
        const serverConfig = window.SERVER_CONFIGS?.[serverName];
        if (!serverConfig) {
            throw new Error('Server config not found');
        }
        
        const apiUrl = serverConfig.api_url;
        
        // Step 1: Upload file to /upload/ endpoint
        const uploadFormData = new FormData();
        uploadFormData.append('file', audioBlob, `recording_${Date.now()}.webm`);
        
        const uploadResponse = await fetch(`${apiUrl}/upload/`, {
            method: 'POST',
            body: uploadFormData
        });
        
        if (!uploadResponse.ok) {
            const errorText = await uploadResponse.text();
            throw new Error(`Upload error: ${errorText}`);
        }
        
        const uploadResult = await uploadResponse.json();
        const filePath = uploadResult.file_path;
        const fileName = uploadResult.filename;
        
        updateRecordStatus('📤 Sending to transcription...');
        updateCaptionStatus('Status: Sending to transcription service...');
        
        // Step 2: Send to transcription service with file_path
        const transcriptionPayload = {
            file_path: filePath,
            file_name: fileName,
            language: 'th',
            model_size: 'base',
            chunk_duration: 3,
            use_chunking: true,
            display_mode: 'realtime_chunks' // Close Caption mode (priority queue)
        };
        
        const transcriptionResponse = await fetch(`${apiUrl}/transcribe/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(transcriptionPayload)
        });
        
        if (!transcriptionResponse.ok) {
            const errorText = await transcriptionResponse.text();
            throw new Error(`Transcription service error: ${errorText}`);
        }
        
        const result = await transcriptionResponse.json();
        const taskId = result.task_id;
        
        liveStreamingState.currentTaskId = taskId;
        updateRecordStatus('✅ Audio uploaded - Processing...');
        updateCaptionStatus(`Status: Processing (Task ID: ${taskId.substring(0, 16)}...)`);
        
        // Start polling for results
        pollTranscriptionStatus(taskId);
        
    } catch (error) {
        console.error('Error sending audio for transcription:', error);
        updateRecordStatus('❌ Error: ' + error.message);
        updateCaptionStatus('Status: Error - ' + error.message);
    }
}

/**
 * Poll transcription status
 */
async function pollTranscriptionStatus(taskId) {
    const maxAttempts = 60; // 60 attempts = 30 seconds (500ms interval)
    let attempts = 0;
    
    const pollInterval = setInterval(async () => {
        attempts++;
        
        try {
            const serverName = liveStreamingState.serverName;
            const serverConfig = window.SERVER_CONFIGS?.[serverName];
            if (!serverConfig) {
                clearInterval(pollInterval);
                return;
            }
            
            const apiUrl = serverConfig.api_url;
            const response = await fetch(`${apiUrl}/transcribe/${taskId}`);
            
            if (!response.ok) {
                throw new Error(`Failed to get task status: ${response.status}`);
            }
            
            const task = await response.json();
            
            if (task.status === 'completed') {
                clearInterval(pollInterval);
                displayCloseCaption(task);
                updateRecordStatus('✅ Close Caption generated');
                updateCaptionStatus('Status: Completed');
            } else if (task.status === 'failed') {
                clearInterval(pollInterval);
                updateRecordStatus('❌ Transcription failed');
                updateCaptionStatus('Status: Failed - ' + (task.error_message || 'Unknown error'));
            } else if (attempts >= maxAttempts) {
                clearInterval(pollInterval);
                updateRecordStatus('⏱️ Timeout waiting for result');
                updateCaptionStatus('Status: Timeout - Still processing...');
            }
            
        } catch (error) {
            console.error('Error polling transcription status:', error);
            if (attempts >= maxAttempts) {
                clearInterval(pollInterval);
                updateRecordStatus('❌ Error polling status');
                updateCaptionStatus('Status: Error - ' + error.message);
            }
        }
    }, 500); // Poll every 500ms
}

/**
 * Handle webhook updates
 */
function handleWebhookUpdate(event) {
    const { taskId, status, progress, payload } = event.detail;
    
    if (taskId === liveStreamingState.currentTaskId) {
        if (status === 'completed' && payload) {
            displayCloseCaption({
                task_id: taskId,
                status: 'completed',
                chunks: payload.segments || [],
                full_text: payload.text || ''
            });
            updateRecordStatus('✅ Close Caption received');
            updateCaptionStatus('Status: Completed');
        } else if (status === 'failed') {
            updateRecordStatus('❌ Transcription failed');
            updateCaptionStatus('Status: Failed');
        } else {
            updateCaptionStatus(`Status: ${status} (${progress}%)`);
        }
    }
}

/**
 * Display Close Caption
 */
function displayCloseCaption(task) {
    const captionDisplay = document.getElementById('captionDisplay');
    if (!captionDisplay) return;
    
    const chunks = task.chunks || [];
    const fullText = task.full_text || '';
    
    if (chunks.length > 0) {
        // Display latest chunk (most recent 3 seconds)
        const latestChunk = chunks[chunks.length - 1];
        const captionText = latestChunk.text || fullText;
        
        captionDisplay.innerHTML = `
            <div style="text-align: center; padding: 20px; font-size: 24px; font-weight: 600;">
                ${captionText}
            </div>
        `;
        
        // Add to recent captions
        addToRecentCaptions({
            timestamp: new Date().toLocaleTimeString('th-TH'),
            text: captionText,
            taskId: task.task_id
        });
        
    } else if (fullText) {
        captionDisplay.innerHTML = `
            <div style="text-align: center; padding: 20px; font-size: 24px; font-weight: 600;">
                ${fullText}
            </div>
        `;
        
        addToRecentCaptions({
            timestamp: new Date().toLocaleTimeString('th-TH'),
            text: fullText,
            taskId: task.task_id
        });
    } else {
        captionDisplay.innerHTML = `
            <div style="text-align: center; color: #888; padding: 40px;">
                No caption text available
            </div>
        `;
    }
}

/**
 * Add to recent captions list
 */
function addToRecentCaptions(caption) {
    liveStreamingState.recentCaptions.unshift(caption);
    
    // Keep only last 10
    if (liveStreamingState.recentCaptions.length > 10) {
        liveStreamingState.recentCaptions = liveStreamingState.recentCaptions.slice(0, 10);
    }
    
    updateRecentCaptionsList();
}

/**
 * Update recent captions list
 */
function updateRecentCaptionsList() {
    const listEl = document.getElementById('recentCaptionsList');
    if (!listEl) return;
    
    if (liveStreamingState.recentCaptions.length === 0) {
        listEl.innerHTML = `
            <div style="text-align: center; color: var(--apple-gray-3); padding: 20px;">
                No recent captions
            </div>
        `;
        return;
    }
    
    listEl.innerHTML = liveStreamingState.recentCaptions.map((caption, index) => `
        <div style="padding: 12px; margin-bottom: 8px; background: var(--apple-gray-2); border-radius: 4px; border-left: 3px solid var(--apple-blue);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span style="font-size: 11px; color: var(--apple-gray-4);">${caption.timestamp}</span>
                <span style="font-size: 11px; color: var(--apple-gray-3);">#${index + 1}</span>
            </div>
            <div style="font-size: 14px; color: var(--apple-gray-5); line-height: 1.5;">
                ${caption.text}
            </div>
        </div>
    `).join('');
}

/**
 * Update caption status
 */
function updateCaptionStatus(message) {
    const statusEl = document.getElementById('captionStatus');
    if (statusEl) {
        statusEl.textContent = message;
    }
}

/**
 * Update HLS URL when input changes
 */
document.addEventListener('DOMContentLoaded', () => {
    const hlsUrlInput = document.getElementById('hlsUrl');
    if (hlsUrlInput) {
        hlsUrlInput.addEventListener('change', () => {
            initializeHLSPlayer();
        });
    }
    
    const rtmpUrlInput = document.getElementById('rtmpUrl');
    if (rtmpUrlInput) {
        rtmpUrlInput.addEventListener('change', () => {
            // RTMP URL is for reference only
        });
    }
});

// Export functions
window.startRecording = startRecording;
window.stopRecording = stopRecording;

