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
                <div class="overview-stat-value" style="color: #007aff;">Starting...</div>
                <div class="overview-stat-label">Status</div>
            </div>
        `;
        document.getElementById('testTasksContainer').innerHTML = '<div class="loading">🔄 กำลังส่ง tasks ไปยัง server... กรุณารอสักครู่</div>';
        
        // Poll batch status to get task_ids
        const pollBatchStatus = async () => {
            try {
                const batchStatus = await dashboardAPI.getBatchStatus(batchId);
                if (batchStatus && batchStatus.task_ids && batchStatus.task_ids.length > 0) {
                    testTaskIds = batchStatus.task_ids;
                    // Start refresh loop
                    startTestRefresh();
                } else {
                    // Still waiting for tasks - poll again after 1 second
                    setTimeout(pollBatchStatus, 1000);
                }
            } catch (error) {
                console.error('Error polling batch status:', error);
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
    if (testTaskIds.length === 0) return;

    try {
        const serverName = document.getElementById('testServer').value;
        if (!serverName) return;

        // Fetch all task statuses
        const remoteAPI = new RemoteServerAPI(serverName);
        const tasks = await Promise.all(
            testTaskIds.map(async (taskId) => {
                try {
                    return await remoteAPI.getTaskStatus(taskId);
                } catch (error) {
                    console.error(`Error fetching task ${taskId}:`, error);
                    return null;
                }
            })
        );

        const validTasks = tasks.filter(t => t !== null);

        // Update overview
        updateTestOverview(validTasks);

        // Update task list
        updateTestTaskList(validTasks);
    } catch (error) {
        console.error('Error refreshing test results:', error);
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

function updateTestTaskList(tasks) {
    const container = document.getElementById('testTasksContainer');
    if (!container) return;

    if (tasks.length === 0 && testTaskIds.length === 0) {
        container.innerHTML = '<div class="loading">🔄 กำลังส่ง tasks ไปยัง server... กรุณารอสักครู่</div>';
        return;
    }
    
    if (tasks.length === 0 && testTaskIds.length > 0) {
        // Tasks are being created but not yet available
        container.innerHTML = `
            <div class="loading">
                ⏳ กำลังสร้าง tasks... (${testTaskIds.length} tasks)
                <br><small style="color: var(--apple-gray-3);">รอสักครู่แล้วจะอัพเดทอัตโนมัติ</small>
            </div>
        `;
        return;
    }

    container.innerHTML = tasks.map((task, index) => {
        const taskId = task.task_id || task.id || testTaskIds[index] || 'N/A';
        const status = (task.status || 'unknown').toLowerCase();
        const progress = task.progress || 0;
        const stepInfo = task.current_stage || task.current_stage_description || task.stage || 'N/A';
        const fileName = task.file_name || task.filename || (task.file_path ? task.file_path.split('/').pop() : 'N/A');
        
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
                    <div class="test-task-id" title="${taskId}">Task #${index + 1}: ${taskId.substring(0, 24)}...</div>
                    <span class="log-item-status ${statusClass}">${status}</span>
                </div>
                <div class="test-task-progress">
                    <div class="progress-bar">
                        <div class="progress-bar-fill" style="width: ${progress}%"></div>
                    </div>
                    <div style="text-align: center; margin-top: 4px; font-size: 12px; color: var(--apple-gray-3); font-weight: 500;">
                        ${progress}%
                    </div>
                </div>
                <div class="test-task-info">
                    <div class="test-task-info-item">
                        <div class="test-task-info-label">📁 File</div>
                        <div class="test-task-info-value">${fileName.length > 35 ? fileName.substring(0, 35) + '...' : fileName}${durationInfo}</div>
                    </div>
                    <div class="test-task-info-item">
                        <div class="test-task-info-label">⚙️ Step</div>
                        <div class="test-task-info-value">${stepInfo}</div>
                    </div>
                    <div class="test-task-info-item">
                        <div class="test-task-info-label">🕐 Updated</div>
                        <div class="test-task-info-value">${formatDate(task.updated_at || task.created_at)}</div>
                    </div>
                    ${status === 'completed' ? (() => {
                        const times = [];
                        if (task.audio_extraction_time && task.audio_extraction_time > 0) {
                            times.push(`🎵 Extract: ${formatTimeDuration(task.audio_extraction_time)}`);
                        }
                        if (task.transcription_time && task.transcription_time > 0) {
                            times.push(`🎤 Transcribe: ${formatTimeDuration(task.transcription_time)}`);
                        }
                        if (task.processing_time && task.processing_time > 0 && times.length === 0) {
                            times.push(`⏱️ Total: ${formatTimeDuration(task.processing_time)}`);
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

