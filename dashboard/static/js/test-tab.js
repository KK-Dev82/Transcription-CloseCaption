/**
 * Test Tab JavaScript
 */

let testRefreshInterval = null;
const TEST_REFRESH_INTERVAL = 5000; // 5 seconds for test tasks

let testTaskIds = [];

// Utility functions
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        const date = new Date(dateString);
        return date.toLocaleString('th-TH', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (e) {
        return dateString;
    }
}

// Format time duration in seconds to human-readable format (e.g., "1m 30s", "45s")
function formatTimeDuration(seconds) {
    if (!seconds || isNaN(seconds)) return 'N/A';
    const totalSeconds = Math.floor(seconds);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    
    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

function formatDuration(seconds) {
    if (typeof seconds !== 'number' || isNaN(seconds) || seconds < 0) return 'N/A';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
}

async function onTestServerChange() {
    const serverName = document.getElementById('testServer').value;
    const videoSelect = document.getElementById('testVideo');
    const startBtn = document.getElementById('startTestBtn');

    if (!serverName) {
        videoSelect.disabled = true;
        videoSelect.innerHTML = '<option value="">Select Server first</option>';
        startBtn.disabled = true;
        return;
    }

    videoSelect.disabled = true;
    videoSelect.innerHTML = '<option value="">Loading videos...</option>';

    try {
        const data = await dashboardAPI.getServerVideos(serverName);
        
        if (data.error || !data.videos || data.videos.length === 0) {
            videoSelect.innerHTML = '<option value="">No videos found</option>';
            startBtn.disabled = true;
            return;
        }

        videoSelect.innerHTML = '<option value="">Select a video</option>' +
            data.videos.map(video => {
                // Handle different possible field names for file name
                const fileName = video.file_name || video.filename || (video.file_path ? video.file_path.split('/').pop() : 'Unknown');
                // Use duration_formatted if available, otherwise format from duration/duration_seconds
                let durationDisplay = 'N/A';
                if (video.duration_formatted && video.duration_formatted !== 'Unknown') {
                    durationDisplay = video.duration_formatted;
                } else if (video.duration || video.duration_seconds) {
                    const seconds = parseFloat(video.duration || video.duration_seconds);
                    if (!isNaN(seconds) && seconds > 0) {
                        const minutes = Math.floor(seconds / 60);
                        const secs = Math.floor(seconds % 60);
                        durationDisplay = `${minutes}:${secs.toString().padStart(2, '0')}`;
                    }
                }
                const filePath = video.file_path || video.path || '';
                
                return `
                    <option value="${filePath}">
                        ${fileName} (${durationDisplay})
                    </option>
                `;
            }).join('');
        
        videoSelect.disabled = false;
        updateTestStartButton();
    } catch (error) {
        console.error('Error loading videos:', error);
        videoSelect.innerHTML = '<option value="">Error loading videos</option>';
        startBtn.disabled = true;
    }
}

function updateTestStartButton() {
    const serverName = document.getElementById('testServer').value;
    const video = document.getElementById('testVideo').value;
    const count = parseInt(document.getElementById('testCount').value) || 0;
    const startBtn = document.getElementById('startTestBtn');

    startBtn.disabled = !(serverName && video && count >= 1 && count <= 50);
}

async function startTest() {
    const serverName = document.getElementById('testServer').value;
    const video = document.getElementById('testVideo').value;
    const count = parseInt(document.getElementById('testCount').value) || 1;

    if (!serverName || !video || count < 1 || count > 50) {
        alert('Please fill in all fields correctly');
        return;
    }

    const startBtn = document.getElementById('startTestBtn');
    startBtn.disabled = true;
    startBtn.textContent = 'Starting...';

    try {
        // Create tasks
        const videoFiles = Array(count).fill(video);
        const result = await dashboardAPI.startBatchTranscription({
            server_name: serverName,
            video_files: videoFiles,
            concurrency: count,
            model_size: 'medium',
            language: 'th'
        });

        if (result.error) {
            alert(`Error: ${result.error}`);
            startBtn.disabled = false;
            startBtn.textContent = '🚀 Start Test';
            return;
        }

        // Store batch_id and show loading message
        const batchId = result.batch_id;
        testTaskIds = []; // Will be populated after tasks are created
        
        // Show results section immediately with loading state
        const resultsSection = document.getElementById('testResultsSection');
        resultsSection.style.display = 'block';
        
        // Show initial loading message
        document.getElementById('testOverview').innerHTML = `
            <div class="overview-stat">
                <div class="overview-stat-value">${count}</div>
                <div class="overview-stat-label">Total</div>
            </div>
            <div class="overview-stat">
                <div class="overview-stat-value" style="color: #007aff;">0</div>
                <div class="overview-stat-label">Completed</div>
            </div>
            <div class="overview-stat">
                <div class="overview-stat-value" style="color: #ff9500;">0</div>
                <div class="overview-stat-label">Processing</div>
            </div>
            <div class="overview-stat">
                <div class="overview-stat-value" style="color: #007aff;">${count}</div>
                <div class="overview-stat-label">Pending</div>
            </div>
            <div class="overview-stat">
                <div class="overview-stat-value" style="color: #ff3b30;">0</div>
                <div class="overview-stat-label">Failed</div>
            </div>
        `;
        document.getElementById('testTasksContainer').innerHTML = '<div class="loading">🔄 กำลังส่ง tasks ไปยัง server... กรุณารอสักครู่</div>';
        
        // Poll batch status to get task_ids
        let pollAttempts = 0;
        const MAX_POLL_ATTEMPTS = 60; // 60 attempts = 60 seconds max wait
        const pollBatchStatus = async () => {
            pollAttempts++;
            
            // Update loading message
            const container = document.getElementById('testTasksContainer');
            if (container) {
                container.innerHTML = `
                    <div class="loading">
                        ⏳ กำลังสร้าง tasks... (รอ task IDs จาก server)
                        <br><small style="color: var(--apple-gray-3);">Attempt ${pollAttempts}/${MAX_POLL_ATTEMPTS} - รอสักครู่แล้วจะอัพเดทอัตโนมัติ</small>
                    </div>
                `;
            }
            
            try {
                const batchStatus = await dashboardAPI.getBatchStatus(batchId);
                
                if (!batchStatus) {
                    if (pollAttempts >= MAX_POLL_ATTEMPTS) {
                        container.innerHTML = '<div class="error">❌ Timeout: ไม่สามารถรับ task IDs ได้ กรุณาลองใหม่</div>';
                        return;
                    }
                    setTimeout(pollBatchStatus, 1000);
                    return;
                }
                
                // Check if tasks are being sent
                if (batchStatus.status === 'failed') {
                    container.innerHTML = '<div class="error">❌ Batch failed: ไม่สามารถส่ง tasks ได้</div>';
                    return;
                }
                
                // Check if we have task_ids
                if (batchStatus.task_ids && batchStatus.task_ids.length > 0) {
                    testTaskIds = batchStatus.task_ids;
                    console.log(`✅ Got ${testTaskIds.length} task IDs, starting refresh...`);
                    
                    // Clear loading message
                    const container = document.getElementById('testTasksContainer');
                    if (container) {
                        container.innerHTML = '<div class="loading">📡 กำลังโหลด task status...</div>';
                    }
                    
                    // Start refresh loop immediately
                    startTestRefresh();
                } else {
                    // Still waiting for tasks - poll again
                    if (pollAttempts >= MAX_POLL_ATTEMPTS) {
                        container.innerHTML = '<div class="error">❌ Timeout: ไม่ได้รับ task IDs ภายใน 60 วินาที กรุณาลองใหม่</div>';
                        return;
                    }
                    setTimeout(pollBatchStatus, 1000);
                }
            } catch (error) {
                console.error('Error polling batch status:', error);
                
                if (pollAttempts >= MAX_POLL_ATTEMPTS) {
                    const container = document.getElementById('testTasksContainer');
                    if (container) {
                        container.innerHTML = `<div class="error">❌ Error: ${error.message || 'ไม่สามารถเชื่อมต่อกับ server ได้'}</div>`;
                    }
                    return;
                }
                
                // Still try to poll
                setTimeout(pollBatchStatus, 2000);
            }
        };
        
        // Start polling for batch status
        setTimeout(pollBatchStatus, 500); // Wait 500ms for first batch status
        
        // Reset button
        startBtn.disabled = false;
        startBtn.textContent = '🚀 Start Test';
        
        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        console.error('Error starting test:', error);
        alert(`Error: ${error.message}`);
        startBtn.disabled = false;
        startBtn.textContent = '🚀 Start Test';
    }
}

function startTestRefresh() {
    stopTestRefresh();
    if (testTaskIds.length === 0) return;
    
    refreshTestResults();
    testRefreshInterval = setInterval(() => {
        refreshTestResults();
    }, TEST_REFRESH_INTERVAL);
}

function stopTestRefresh() {
    if (testRefreshInterval) {
        clearInterval(testRefreshInterval);
        testRefreshInterval = null;
    }
}

async function refreshTestResults() {
    if (testTaskIds.length === 0) {
        console.warn('No task IDs to refresh');
        return;
    }

    try {
        const serverName = document.getElementById('testServer').value;
        if (!serverName) {
            console.warn('No server selected');
            return;
        }

        // Fetch all task statuses
        const remoteAPI = new RemoteServerAPI(serverName);
        const tasks = await Promise.all(
            testTaskIds.map(async (taskId) => {
                try {
                    const task = await remoteAPI.getTaskStatus(taskId);
                    return task;
                } catch (error) {
                    console.error(`Error fetching task ${taskId.substring(0, 16)}...:`, error);
                    // Return a placeholder task with error status
                    return {
                        task_id: taskId,
                        status: 'error',
                        error_message: `Failed to fetch: ${error.message || 'Connection error'}`,
                        progress: 0
                    };
                }
            })
        );

        const validTasks = tasks.filter(t => t !== null);

        // Update overview
        updateTestOverview(validTasks);

        // Update task list
        updateTestTaskList(validTasks);
        
        // Log refresh status
        const completed = validTasks.filter(t => t.status === 'completed').length;
        const processing = validTasks.filter(t => t.status === 'processing' || t.status === 'transcribing').length;
        const pending = validTasks.filter(t => t.status === 'pending').length;
        const failed = validTasks.filter(t => t.status === 'failed' || t.status === 'error').length;
        
        console.log(`📊 Test refresh: ${completed} completed, ${processing} processing, ${pending} pending, ${failed} failed`);
        
    } catch (error) {
        console.error('Error refreshing test results:', error);
        
        // Show error in UI
        const container = document.getElementById('testTasksContainer');
        if (container && testTaskIds.length > 0) {
            const errorHtml = `
                <div class="error" style="padding: 16px; background: #ffebee; border-radius: 8px; margin-bottom: 16px;">
                    <strong>❌ Error refreshing tasks:</strong> ${error.message || 'Connection error'}
                    <br><small style="color: #666;">Trying to reconnect...</small>
                </div>
            `;
            const currentHtml = container.innerHTML;
            if (!currentHtml.includes('Error refreshing')) {
                container.innerHTML = errorHtml + (currentHtml || '');
            }
        }
    }
}

function updateTestOverview(tasks) {
    const overview = document.getElementById('testOverview');
    if (!overview) return;

    const total = tasks.length;
    const completed = tasks.filter(t => t.status === 'completed').length;
    const processing = tasks.filter(t => t.status === 'processing').length;
    const pending = tasks.filter(t => t.status === 'pending').length;
    const failed = tasks.filter(t => t.status === 'failed').length;

    overview.innerHTML = `
        <div class="overview-stat">
            <div class="overview-stat-value">${total}</div>
            <div class="overview-stat-label">Total</div>
        </div>
        <div class="overview-stat">
            <div class="overview-stat-value" style="color: var(--apple-green);">${completed}</div>
            <div class="overview-stat-label">Completed</div>
        </div>
        <div class="overview-stat">
            <div class="overview-stat-value" style="color: #ff9500;">${processing}</div>
            <div class="overview-stat-label">Processing</div>
        </div>
        <div class="overview-stat">
            <div class="overview-stat-value" style="color: #007aff;">${pending}</div>
            <div class="overview-stat-label">Pending</div>
        </div>
        <div class="overview-stat">
            <div class="overview-stat-value" style="color: #ff3b30;">${failed}</div>
            <div class="overview-stat-label">Failed</div>
        </div>
    `;
}

// Helper function to get step status
function getStepStatus(task, stepName) {
    const status = (task.status || 'unknown').toLowerCase();
    const currentStage = (task.current_stage || '').toLowerCase();
    
    if (stepName === 'pending') {
        // Pending is active when status is pending
        return status === 'pending' ? 'active' : 
               (status === 'processing' || status === 'transcribing' || status === 'completed' || status === 'failed') ? 'completed' : 'pending';
    } else if (stepName === 'in_queue') {
        // In queue is active when status is processing but stage hasn't started yet
        return (status === 'processing' && !currentStage) || (status === 'processing' && currentStage === 'queued') ? 'active' :
               (currentStage === 'extracting_audio' || currentStage === 'downloading' || currentStage === 'transcribing' || 
                currentStage === 'merging' || currentStage === 'finalizing' || status === 'completed' || status === 'failed') ? 'completed' : 'pending';
    } else if (stepName === 'audio_extraction') {
        // Audio extraction is active when stage is extracting_audio or downloading
        return currentStage === 'extracting_audio' || currentStage === 'downloading' ? 'active' :
               (currentStage === 'transcribing' || currentStage === 'merging' || currentStage === 'finalizing' || 
                status === 'completed' || status === 'failed') ? 'completed' : 'pending';
    } else if (stepName === 'transcribe') {
        // Transcribe is active when stage is transcribing
        return currentStage === 'transcribing' ? 'active' :
               (currentStage === 'merging' || currentStage === 'finalizing' || status === 'completed' || status === 'failed') ? 'completed' : 'pending';
    } else if (stepName === 'completed') {
        // Completed step shows completed or failed
        return status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : 'pending';
    }
    return 'pending';
}

// Helper function to get step display name
function getStepDisplayName(stepName) {
    const stepNames = {
        'pending': 'Pending',
        'in_queue': 'In Queue',
        'audio_extraction': 'Audio Extraction',
        'transcribe': 'Transcribe',
        'completed': 'Completed'
    };
    return stepNames[stepName] || stepName;
}

function updateTestTaskList(tasks) {
    const container = document.getElementById('testTasksContainer');
    if (!container) return;

    if (tasks.length === 0 && testTaskIds.length === 0) {
        container.innerHTML = '<div class="loading">🔄 กำลังส่ง tasks ไปยัง server... กรุณารอสักครู่</div>';
        return;
    }
    
    if (tasks.length === 0 && testTaskIds.length > 0) {
        // Tasks are being created but not yet available
        // Check if we're still polling for task IDs or if we have them but can't fetch status
        const hasError = container.innerHTML.includes('Error');
        if (!hasError) {
            container.innerHTML = `
                <div class="loading">
                    ⏳ กำลังโหลด task status... (${testTaskIds.length} tasks)
                    <br><small style="color: var(--apple-gray-3);">รอสักครู่แล้วจะอัพเดทอัตโนมัติ</small>
                </div>
            `;
        }
        return;
    }

    // Sort tasks by creation time or keep original order
    const sortedTasks = [...tasks].sort((a, b) => {
        const aTime = new Date(a.created_at || 0);
        const bTime = new Date(b.created_at || 0);
        return aTime - bTime;
    });

    container.innerHTML = sortedTasks.map((task, index) => {
        const taskId = task.task_id || task.id || testTaskIds[index] || 'N/A';
        const status = (task.status || 'unknown').toLowerCase();
        const progress = task.progress || 0;
        const currentStage = (task.current_stage || '').toLowerCase();
        const stageDescription = task.current_stage_description || task.current_stage || 'N/A';
        const fileName = task.file_name || task.filename || (task.file_path ? task.file_path.split('/').pop() : 'N/A');
        
        // Get step statuses
        const steps = ['pending', 'in_queue', 'audio_extraction', 'transcribe', 'completed'];
        const stepStatuses = steps.map(step => ({
            name: step,
            displayName: getStepDisplayName(step),
            status: getStepStatus(task, step)
        }));
        
        // Render step progress
        const stepsHtml = stepStatuses.map((step, stepIndex) => {
            let stepClass = 'step-pending';
            let stepIcon = '⏸️';
            let stepText = step.displayName;
            
            if (step.status === 'active') {
                stepClass = 'step-active';
                stepIcon = '⏳';
            } else if (step.status === 'completed') {
                stepClass = 'step-completed';
                stepIcon = '✅';
            } else if (step.status === 'failed' && step.name === 'completed') {
                stepClass = 'step-failed';
                stepIcon = '❌';
                stepText = 'Failed';
            }
            
            const arrow = stepIndex < stepStatuses.length - 1 ? ' → ' : '';
            
            return `<span class="step-item ${stepClass}">${stepIcon} ${stepText}</span>${arrow}`;
        }).join('');
        
        // Get video duration if available
        let durationInfo = '';
        const duration = task.total_duration || task.video_duration || task.duration || task.duration_seconds;
        if (duration && typeof duration === 'number' && duration > 0) {
            const minutes = Math.floor(duration / 60);
            const seconds = Math.floor(duration % 60);
            durationInfo = ` (${minutes}:${seconds.toString().padStart(2, '0')})`;
        }
        
        // Get transcribed text
        const fullText = task.full_text || task.corrected_text || task.original_text || '';
        const isCompleted = status === 'completed' && progress >= 100;
        
        const statusClass = status === 'completed' ? 'completed' : 
                           status === 'processing' || status === 'transcribing' ? 'processing' :
                           status === 'pending' ? 'pending' :
                           status === 'failed' || status === 'error' ? 'failed' : 'pending';

        return `
            <div class="test-task-item ${statusClass}">
                <div class="test-task-header">
                    <div class="test-task-id" title="${taskId}">
                        <strong>${index + 1}. Task ID:</strong> ${taskId.substring(0, 32)}...
                    </div>
                </div>
                <div class="test-task-progress">
                    <div class="progress-bar">
                        <div class="progress-bar-fill" style="width: ${progress}%"></div>
                    </div>
                    <div style="text-align: center; margin-top: 4px; font-size: 14px; color: var(--apple-gray-4); font-weight: 600;">
                        Progress: ${progress}%
                    </div>
                </div>
                <div class="test-task-steps">
                    <div style="font-weight: 600; margin-bottom: 8px; color: var(--apple-gray-4);">Step Processing:</div>
                    <div class="step-progress-container">
                        ${stepsHtml}
                    </div>
                </div>
                <div class="test-task-info">
                    <div class="test-task-info-item">
                        <div class="test-task-info-label">📁 File</div>
                        <div class="test-task-info-value">${fileName.length > 35 ? fileName.substring(0, 35) + '...' : fileName}${durationInfo}</div>
                    </div>
                    <div class="test-task-info-item">
                        <div class="test-task-info-label">⚙️ Current Stage</div>
                        <div class="test-task-info-value">${stageDescription}</div>
                    </div>
                    <div class="test-task-info-item">
                        <div class="test-task-info-label">🕐 Updated</div>
                        <div class="test-task-info-value">${formatDate(task.updated_at || task.created_at)}</div>
                    </div>
                    ${status === 'completed' ? (() => {
                        const times = [];
                        // Check audio_extraction_time (may be null/undefined)
                        const audioTime = task.audio_extraction_time || task.audio_extraction_time === 0 ? parseFloat(task.audio_extraction_time) : null;
                        if (audioTime !== null && !isNaN(audioTime) && audioTime > 0) {
                            times.push(`🎵 Extract: ${formatTimeDuration(audioTime)}`);
                        }
                        // Check transcription_time (may be null/undefined)
                        const transcribeTime = task.transcription_time || task.transcription_time === 0 ? parseFloat(task.transcription_time) : null;
                        if (transcribeTime !== null && !isNaN(transcribeTime) && transcribeTime > 0) {
                            times.push(`🎤 Transcribe: ${formatTimeDuration(transcribeTime)}`);
                        }
                        // Fallback to processing_time if no specific times available
                        const processingTime = task.processing_time || task.time_used || (task.processing_time === 0 ? 0 : null);
                        if (processingTime !== null && !isNaN(processingTime) && processingTime > 0 && times.length === 0) {
                            times.push(`⏱️ Total: ${formatTimeDuration(processingTime)}`);
                        }
                        return times.length > 0 ? `
                    <div class="test-task-info-item">
                        <div class="test-task-info-label">⏱️ Time Used</div>
                        <div class="test-task-info-value" style="display: flex; gap: 12px; flex-wrap: wrap;">${times.join(' • ')}</div>
                    </div>
                        ` : '';
                    })() : ''}
                </div>
                ${isCompleted && fullText ? `
                    <div class="test-task-text visible">
                        <strong>📝 Transcribed Text:</strong>
                        <div style="margin-top: 8px; padding: 12px; background: #f5f5f5; border-radius: 6px; font-size: 14px; line-height: 1.6; max-height: 200px; overflow-y: auto;">
                            ${fullText.substring(0, 1000)}${fullText.length > 1000 ? '...' : ''}
                        </div>
                    </div>
                ` : ''}
                ${task.error_message ? `
                    <div class="test-task-error">
                        <strong>❌ Error:</strong> ${task.error_message}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

// Export functions
window.onTestServerChange = onTestServerChange;
window.startTest = startTest;
window.updateTestStartButton = updateTestStartButton;
window.startTestRefresh = startTestRefresh;
window.stopTestRefresh = stopTestRefresh;

