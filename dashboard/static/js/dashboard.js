// Transcription Service Dashboard JavaScript - Multi-Server Support

let autoRefreshInterval = null;
let historyRefreshInterval = null;
const TRACKING_REFRESH_INTERVAL = 5000; // 5 seconds - for summary, worker status, queues
const HISTORY_REFRESH_INTERVAL = 30000; // 30 seconds - for task list (history)
const SERVERS = ['4000-ada-sc', '4000-ada', '5080']; // 4000-ada-sc is default (when 4000-ada GPU is full)

// SERVER_CONFIGS is imported from api-client.js via window.SERVER_CONFIGS
// Use window.SERVER_CONFIGS to avoid redeclaration error

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeServers();
    refreshData();
    setupAutoRefresh();
});

function initializeServers() {
    const container = document.getElementById('serversContainer');
    if (!container) return;

    container.innerHTML = SERVERS.map(serverName => `
        <div class="server-section" id="server-${serverName}">
            <div class="server-header">
                <div>
                    <h2 class="server-title">${serverName}</h2>
                    <span class="server-status-badge" id="server-${serverName}-status">
                        <span class="status-dot"></span>
                        <span>Checking...</span>
                    </span>
                </div>
                <div>
                    <button class="btn btn-danger" onclick="clearStuckTasks('${serverName}')" style="font-size: 14px; padding: 8px 16px;">
                        🧹 Clear Stuck Tasks
                    </button>
                </div>
            </div>

            <!-- Summary Cards -->
            <div class="status-grid" id="server-${serverName}-summary">
                <div class="status-card">
                    <h3>Total Tasks</h3>
                    <div class="value" id="server-${serverName}-total">-</div>
                </div>
                <div class="status-card completed">
                    <h3>Completed</h3>
                    <div class="value" id="server-${serverName}-completed">-</div>
                </div>
                <div class="status-card processing">
                    <h3>Processing</h3>
                    <div class="value" id="server-${serverName}-processing">-</div>
                </div>
                <div class="status-card pending">
                    <h3>Pending</h3>
                    <div class="value" id="server-${serverName}-pending">-</div>
                </div>
                <div class="status-card failed">
                    <h3>Failed</h3>
                    <div class="value" id="server-${serverName}-failed">-</div>
                </div>
                <div class="status-card stuck">
                    <h3>Stuck</h3>
                    <div class="value" id="server-${serverName}-stuck">-</div>
                </div>
            </div>

            <!-- Worker Status -->
            <div class="worker-status">
                <h3>Worker Status</h3>
                <div class="info" id="server-${serverName}-worker">
                    <div class="info-item">
                        <label>Status</label>
                        <div class="value">
                            <span class="status-badge" id="server-${serverName}-worker-status">-</span>
                        </div>
                    </div>
                    <div class="info-item">
                        <label>PID</label>
                        <div class="value" id="server-${serverName}-worker-pid">-</div>
                    </div>
                    <div class="info-item">
                        <label>Uptime</label>
                        <div class="value" id="server-${serverName}-worker-uptime">-</div>
                    </div>
                    <div class="info-item">
                        <label>Health</label>
                        <div class="value" id="server-${serverName}-health">-</div>
                    </div>
                </div>
            </div>

            <!-- Queue Status -->
            <div class="worker-status">
                <h3>RabbitMQ Queues</h3>
                <div id="server-${serverName}-queues">
                    <div class="loading">Loading queue status...</div>
                </div>
            </div>

            <!-- Tasks Table -->
            <div class="tasks-section">
                <div class="controls">
                    <button class="btn btn-primary" onclick="refreshServerTasks('${serverName}')" title="Manually refresh task list">🔄 Refresh Tasks</button>
                    <span class="refresh-indicator" id="server-${serverName}-historyRefresh" style="margin-left: 10px; font-size: 12px; color: #666;">Auto-refresh: 30s</span>
                    <select id="server-${serverName}-statusFilter" onchange="refreshServerTasks('${serverName}')">
                        <option value="">All Status</option>
                        <option value="pending">Pending</option>
                        <option value="processing">Processing</option>
                        <option value="completed">Completed</option>
                        <option value="failed">Failed</option>
                        <option value="stopped">Stopped</option>
                    </select>
                    <select id="server-${serverName}-limitFilter" onchange="refreshServerTasks('${serverName}')">
                        <option value="20">Show 20</option>
                        <option value="50">Show 50</option>
                        <option value="100">Show 100</option>
                    </select>
                </div>
                <div id="server-${serverName}-tasksInfo" style="margin-bottom: 12px; font-size: 14px; color: var(--apple-gray-3);">
                    <span id="server-${serverName}-tasksCount">-</span>
                </div>
                <table class="tasks-table">
                    <thead>
                        <tr>
                            <th>Task ID</th>
                            <th>Status</th>
                            <th>Progress</th>
                            <th>File Name</th>
                            <th>Text Length</th>
                            <th>Updated At</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="server-${serverName}-tasks">
                        <tr>
                            <td colspan="7" class="loading">Loading tasks...</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    `).join('');
}

function setupAutoRefresh() {
    const checkbox = document.getElementById('autoRefresh');
    checkbox.addEventListener('change', (e) => {
        if (e.target.checked) {
            startAutoRefresh();
        } else {
            stopAutoRefresh();
        }
    });
    startAutoRefresh();
}

function startAutoRefresh() {
    // Stop existing intervals
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    if (historyRefreshInterval) {
        clearInterval(historyRefreshInterval);
    }
    
    // Refresh tracking status (summary, worker, queues) frequently - every 5s
    autoRefreshInterval = setInterval(() => {
        refreshTrackingStatus();
        const indicator = document.getElementById('refreshIndicator');
        if (indicator) {
            indicator.style.background = '#34c759';
            setTimeout(() => {
                indicator.style.background = '#34c759';
            }, 500);
        }
    }, TRACKING_REFRESH_INTERVAL);
    
    // Refresh history (task list) less frequently - every 30s
    historyRefreshInterval = setInterval(() => {
        refreshHistory();
    }, HISTORY_REFRESH_INTERVAL);
    
    // Initial history refresh after 5 seconds
    setTimeout(() => {
        refreshHistory();
    }, 5000);
    
    // Update refresh interval display
    const intervalDisplay = document.getElementById('refreshInterval');
    if (intervalDisplay) {
        intervalDisplay.textContent = '5s (status) / 30s (tasks)';
    }
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
    if (historyRefreshInterval) {
        clearInterval(historyRefreshInterval);
        historyRefreshInterval = null;
    }
    
    // Reset refresh interval display
    const intervalDisplay = document.getElementById('refreshInterval');
    if (intervalDisplay) {
        intervalDisplay.textContent = '5';
    }
}

// Refresh tracking status (summary, worker status, queues) - called frequently (every 5s)
async function refreshTrackingStatus() {
    await Promise.all(SERVERS.map(serverName => 
        Promise.all([
            refreshServerSummary(serverName),
            refreshServerStatus(serverName),
            refreshServerQueues(serverName)
        ])
    ));
}

// Refresh history (task list) - called less frequently (every 30s)
async function refreshHistory() {
    await Promise.all(SERVERS.map(serverName => 
        refreshServerTasks(serverName)
    ));
}

// Legacy function - refresh everything (used for manual "Refresh Now" button)
async function refreshData() {
    await Promise.all([
        refreshTrackingStatus(),
        refreshHistory()
    ]);
}

// Legacy function - refresh all data for a specific server (used internally)
async function refreshServerData(serverName) {
    await Promise.all([
        refreshServerSummary(serverName),
        refreshServerStatus(serverName),
        refreshServerQueues(serverName),
        refreshServerTasks(serverName)
    ]);
}

async function refreshServerSummary(serverName) {
    try {
        const data = await dashboardAPI.getServerSummary(serverName);
        
        if (data.error) {
            updateServerStatus(serverName, false);
            setServerValue(serverName, 'total', '-');
            setServerValue(serverName, 'completed', '-');
            setServerValue(serverName, 'processing', '-');
            setServerValue(serverName, 'pending', '-');
            setServerValue(serverName, 'failed', '-');
            setServerValue(serverName, 'stuck', '-');
            return;
        }

        updateServerStatus(serverName, true);
        
        const setValue = (field, value) => {
            setServerValue(serverName, field, value);
        };
        
        setValue('total', data.total || 0);
        setValue('completed', data.completed || 0);
        setValue('processing', data.processing || 0);
        setValue('pending', data.pending || 0);
        setValue('failed', data.failed || 0);
        setValue('stuck', data.stuck || 0);
    } catch (error) {
        console.error(`Error fetching summary for ${serverName}:`, error);
        updateServerStatus(serverName, false);
    }
}

async function refreshServerStatus(serverName) {
    try {
        const data = await dashboardAPI.getServerStatus(serverName);
        
        if (data.error) {
            updateServerStatus(serverName, false);
            setServerValue(serverName, 'health', 'Unreachable');
            setServerValue(serverName, 'worker-status', '-');
            setServerValue(serverName, 'worker-pid', '-');
            setServerValue(serverName, 'worker-uptime', '-');
            return;
        }

        // Health
        const healthEl = document.getElementById(`server-${serverName}-health`);
        if (healthEl) {
            const health = data.health || 'unknown';
            healthEl.textContent = health.charAt(0).toUpperCase() + health.slice(1);
        }

        // Worker Status
        if (data.worker && !data.worker.error) {
            const statusBadge = document.getElementById(`server-${serverName}-worker-status`);
            if (statusBadge) {
                if (data.worker.is_running) {
                    statusBadge.textContent = 'Running';
                    statusBadge.className = 'status-badge running';
                } else {
                    statusBadge.textContent = 'Stopped';
                    statusBadge.className = 'status-badge stopped';
                }
            }
            
            setServerValue(serverName, 'worker-pid', data.worker.pid || 'N/A');
            setServerValue(serverName, 'worker-uptime', data.worker.uptime || 'N/A');
        } else {
            setServerValue(serverName, 'worker-status', 'N/A');
            setServerValue(serverName, 'worker-pid', 'N/A');
            setServerValue(serverName, 'worker-uptime', 'N/A');
        }
    } catch (error) {
        console.error(`Error fetching status for ${serverName}:`, error);
        updateServerStatus(serverName, false);
    }
}

async function refreshServerQueues(serverName) {
    try {
        const response = await fetch(`/api/server/${serverName}/status`);
        const data = await response.json();
        
        const container = document.getElementById(`server-${serverName}-queues`);
        if (!container) return;
        
        if (data.queues && !data.queues.error && data.queues.queues && data.queues.queues.length > 0) {
            container.innerHTML = `
                <div class="info">
                    ${data.queues.queues.map(queue => `
                        <div class="queue-item">
                            <label>${queue.name}</label>
                            <div class="value">
                                Ready: ${queue.messages_ready}<br>
                                Unacked: ${queue.messages_unacknowledged}<br>
                                Consumers: ${queue.consumers}
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        } else {
            container.innerHTML = '<div class="loading">Queue data unavailable</div>';
        }
    } catch (error) {
        console.error(`Error fetching queues for ${serverName}:`, error);
        const container = document.getElementById(`server-${serverName}-queues`);
        if (container) {
            container.innerHTML = '<div class="error">Error loading queue status</div>';
        }
    }
}

// Legacy alias for compatibility (used in HTML onclick="refreshTasks()")
function refreshTasks(serverName) {
    return refreshServerTasks(serverName);
}

// Update history refresh countdown indicator
function updateHistoryRefreshIndicator(serverName) {
    const indicator = document.getElementById(`server-${serverName}-historyRefresh`);
    if (!indicator) return;
    
    let secondsLeft = HISTORY_REFRESH_INTERVAL / 1000;
    
    // Clear any existing countdown
    if (indicator._countdownInterval) {
        clearInterval(indicator._countdownInterval);
    }
    
    // Start countdown
    indicator._countdownInterval = setInterval(() => {
        secondsLeft--;
        if (indicator && secondsLeft >= 0) {
            indicator.textContent = `Auto-refresh: ${secondsLeft}s`;
            indicator.style.color = secondsLeft <= 5 ? '#ff3b30' : '#666';
        } else {
            clearInterval(indicator._countdownInterval);
            indicator._countdownInterval = null;
        }
    }, 1000);
    
    // Reset after refresh interval
    setTimeout(() => {
        if (indicator._countdownInterval) {
            clearInterval(indicator._countdownInterval);
            indicator._countdownInterval = null;
        }
        if (indicator) {
            indicator.textContent = 'Auto-refresh: 30s';
            indicator.style.color = '#666';
        }
    }, HISTORY_REFRESH_INTERVAL);
}

async function refreshServerTasks(serverName) {
    // Update refresh indicator countdown
    updateHistoryRefreshIndicator(serverName);
    
    const statusFilterEl = document.getElementById(`server-${serverName}-statusFilter`);
    const limitFilterEl = document.getElementById(`server-${serverName}-limitFilter`);
    const statusFilter = statusFilterEl ? statusFilterEl.value : '';
    const limit = limitFilterEl ? parseInt(limitFilterEl.value) || 20 : 20;
    
    const tbody = document.getElementById(`server-${serverName}-tasks`);
    const infoEl = document.getElementById(`server-${serverName}-tasksInfo`);
    if (!tbody) return;
    
    tbody.innerHTML = '<tr><td colspan="7" class="loading">Loading tasks...</td></tr>';
    
    try {
        const data = await dashboardAPI.getServerTasks(serverName, {
            limit,
            status: statusFilter || null,
            timeout: 30
        });
        
        if (data.error) {
            console.error(`API returned error for ${serverName}:`, data);
            const errorDetails = data.error_details || '';
            const apiUrl = data.api_url || '';
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="error">
                        <div style="padding: 16px;">
                            <strong style="color: #ff3b30;">Error: ${data.error}</strong>
                            ${errorDetails ? `<br><code style="font-size: 12px; color: #666; margin-top: 8px; display: block;">${errorDetails.substring(0, 200)}${errorDetails.length > 200 ? '...' : ''}</code>` : ''}
                            ${apiUrl ? `<br><small style="color: #999; margin-top: 4px; display: block;">API URL: ${apiUrl}/transcribe/</small>` : ''}
                        </div>
                    </td>
                </tr>
            `;
            if (infoEl) {
                infoEl.innerHTML = `<span style="color: #ff3b30;">Error: ${data.error}</span>`;
            }
            return;
        }
        
        const tasks = data.tasks || [];
        const total = data.total || 0;
        const showing = data.showing || tasks.length;
        const statusCount = data.status_count || {};
        
        // Update info
        if (infoEl) {
            let infoText = `Showing ${showing} of ${total} tasks`;
            if (statusFilter) {
                infoText += ` (filtered: ${statusFilter})`;
            }
            if (Object.keys(statusCount).length > 0) {
                const counts = Object.entries(statusCount)
                    .map(([status, count]) => `${status}: ${count}`)
                    .join(', ');
                infoText += ` | ${counts}`;
            }
            infoEl.innerHTML = `<span>${infoText}</span>`;
        }
        
        if (tasks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading">No tasks found</td></tr>';
            return;
        }
        
        // Render tasks table
        tbody.innerHTML = tasks.map(task => {
            const taskId = task.task_id || task.id || 'N/A';
            const status = (task.status || 'unknown').toLowerCase();
            const progress = task.progress || 0;
            const fileName = task.file_name || task.filename || 'N/A';
            const textLength = task.full_text ? task.full_text.length : (task.text_length || 0);
            const updatedAt = task.updated_at || task.created_at || '';
            
            const statusClass = status === 'completed' ? 'completed' : 
                               status === 'processing' ? 'processing' :
                               status === 'pending' ? 'pending' :
                               status === 'failed' || status === 'stopped' ? 'failed' : 'pending';
            
            return `
                <tr>
                    <td>
                        <a href="${window.SERVER_CONFIGS?.[serverName]?.api_url || ''}/transcribe/${taskId}" target="_blank" title="${taskId}">
                            ${taskId.substring(0, 16)}...
                        </a>
                    </td>
                    <td>
                        <span class="status-indicator ${statusClass}"></span>
                        ${status}
                    </td>
                    <td>
                        <div class="progress-bar">
                            <div class="progress-bar-fill" style="width: ${progress}%"></div>
                        </div>
                        ${progress}%
                    </td>
                    <td title="${fileName}">${fileName.length > 40 ? fileName.substring(0, 40) + '...' : fileName}</td>
                    <td>${textLength.toLocaleString()} chars</td>
                    <td>${formatDate(updatedAt)}</td>
                    <td>
                        ${status === 'failed' || status === 'stopped' ? 
                            `<button class="btn btn-success" onclick="retryServerTask('${serverName}', '${taskId}')" style="font-size: 12px; padding: 4px 8px;">Retry</button>` : 
                            ''
                        }
                        ${status === 'pending' || status === 'processing' ?
                            `<button class="btn btn-danger" onclick="cancelServerTask('${serverName}', '${taskId}')" style="font-size: 12px; padding: 4px 8px;">Cancel</button>` :
                            ''
                        }
                    </td>
                </tr>
            `;
        }).join('');
        
    } catch (error) {
        console.error(`Error fetching tasks for ${serverName}:`, error);
        const tbody = document.getElementById(`server-${serverName}-tasks`);
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="7" class="error">Error loading tasks</td></tr>';
        }
    }
}

async function retryServerTask(serverName, taskId) {
    if (!confirm(`Retry task ${taskId.substring(0, 16)}... on ${serverName}?`)) {
        return;
    }
    try {
        const serverConfig = window.SERVER_CONFIGS?.[serverName];
        if (!serverConfig) {
            alert('Server not found');
            return;
        }
        const response = await fetch(`${serverConfig.api_url}/v2/tasks/${taskId}/retry`, {
            method: 'POST'
        });
        const data = await response.json().catch(() => ({}));
        if (response.ok && data.success) {
            alert('Task retry initiated successfully');
            refreshServerTasks(serverName);
        } else {
            alert(`Failed to retry: ${data.message || data.detail || response.statusText}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function cancelServerTask(serverName, taskId) {
    if (!confirm(`Cancel task ${taskId.substring(0, 16)}... on ${serverName}?`)) {
        return;
    }
    
    try {
        const serverConfig = window.SERVER_CONFIGS?.[serverName];
        if (!serverConfig) {
            alert('Server not found');
            return;
        }
        
        const response = await fetch(`${serverConfig.api_url}/transcribe/${taskId}`, {
            method: 'DELETE'
        });
        
        if (response.status === 200) {
            alert('Task cancelled successfully');
            refreshServerTasks(serverName);
        } else {
            const error = await response.text();
            alert(`Failed to cancel task: ${error}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

function setServerValue(serverName, field, value) {
    const el = document.getElementById(`server-${serverName}-${field}`);
    if (el) el.textContent = value;
}

function updateServerStatus(serverName, isOnline) {
    const badge = document.getElementById(`server-${serverName}-status`);
    if (badge) {
        if (isOnline) {
            badge.className = 'server-status-badge online';
            badge.innerHTML = '<span class="status-dot"></span><span>Online</span>';
        } else {
            badge.className = 'server-status-badge offline';
            badge.innerHTML = '<span class="status-dot"></span><span>Offline</span>';
        }
    }
}

async function deleteTask(taskId) {
    if (!confirm(`Delete task ${taskId}? This cannot be undone.`)) return;
    
    try {
        const response = await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.success) {
            alert('Task deleted successfully');
            refreshData();
        } else {
            alert('Error deleting task');
        }
    } catch (error) {
        alert('Error deleting task: ' + error.message);
    }
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        const date = new Date(dateString);
        return date.toLocaleString('th-TH');
    } catch {
        return dateString;
    }
}

// Batch Transcription Controller
let currentBatchId = null;
let batchProgressInterval = null;

async function onServerChange() {
    const serverName = document.getElementById('controllerServer').value;
    const videosList = document.getElementById('videosList');
    const startBtn = document.getElementById('startBatchBtn');
    
    if (!serverName) {
        videosList.innerHTML = '<div class="loading">Select a server first</div>';
        startBtn.disabled = true;
        return;
    }
    
    videosList.innerHTML = '<div class="loading">Loading videos...</div>';
    startBtn.disabled = true;
    
    try {
        const data = await dashboardAPI.getServerVideos(serverName);
        
        if (data.error) {
            videosList.innerHTML = `<div class="error">Error: ${data.error}</div>`;
            return;
        }
        
        const videos = data.videos || [];
        if (videos.length === 0) {
            videosList.innerHTML = '<div class="loading">No videos found in /uploads</div>';
            return;
        }
        
        videosList.innerHTML = videos.map((video, index) => `
            <div class="video-item">
                <input type="checkbox" id="video-${index}" value="${video.file_path || video.filename}" data-duration="${video.duration || 0}">
                <div class="video-info">
                    <div class="video-name">${video.filename || video.file_path}</div>
                    <div class="video-meta">
                        ${video.duration_formatted ? `Duration: ${video.duration_formatted}` : ''}
                        ${video.file_size ? ` • ${(video.file_size / 1024 / 1024).toFixed(2)} MB` : ''}
                    </div>
                </div>
            </div>
        `).join('');
        
        startBtn.disabled = false;
    } catch (error) {
        console.error('Error loading videos:', error);
        videosList.innerHTML = `<div class="error">Error loading videos: ${error.message}</div>`;
    }
}

async function startBatchTranscription() {
    const serverName = document.getElementById('controllerServer').value;
    const concurrency = parseInt(document.getElementById('controllerConcurrency').value) || 1;
    const modelSize = document.getElementById('controllerModelSize').value;
    
    if (!serverName) {
        alert('Please select a server');
        return;
    }
    
    // Get selected videos
    const checkboxes = document.querySelectorAll('#videosList input[type="checkbox"]:checked');
    const selectedVideos = Array.from(checkboxes).map(cb => cb.value);
    
    if (selectedVideos.length === 0) {
        alert('Please select at least one video');
        return;
    }
    
    // Disable button
    const startBtn = document.getElementById('startBatchBtn');
    startBtn.disabled = true;
    startBtn.textContent = 'Starting...';
    
    try {
        const response = await fetch('/api/batch/transcription', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                server_name: serverName,
                video_files: selectedVideos,
                concurrency: concurrency,
                language: 'th',
                model_size: modelSize,
                use_chunking: false
            })
        });
        
        const data = await response.json();
        
        if (response.status !== 200) {
            alert(`Error: ${data.detail || data.error || 'Unknown error'}`);
            startBtn.disabled = false;
            startBtn.textContent = 'Start Batch Transcription';
            return;
        }
        
        currentBatchId = data.batch_id;
        
        // Show progress section
        document.getElementById('batchProgress').style.display = 'block';
        
        // Start polling for progress
        startBatchProgressPolling();
        
        startBtn.disabled = false;
        startBtn.textContent = 'Start Batch Transcription';
    } catch (error) {
        console.error('Error starting batch:', error);
        alert(`Error: ${error.message}`);
        startBtn.disabled = false;
        startBtn.textContent = 'Start Batch Transcription';
    }
}

function startBatchProgressPolling() {
    if (batchProgressInterval) {
        clearInterval(batchProgressInterval);
    }
    
    batchProgressInterval = setInterval(async () => {
        if (!currentBatchId) {
            clearInterval(batchProgressInterval);
            return;
        }
        
        try {
            const batchStatus = await dashboardAPI.getBatchStatus(currentBatchId);
            
            updateBatchProgress(batchStatus);
            
            // Stop polling if complete
            if (batchStatus.completed_tasks + batchStatus.failed_tasks === batchStatus.total_tasks) {
                clearInterval(batchProgressInterval);
            }
        } catch (error) {
            console.error('Error polling batch progress:', error);
        }
    }, 2000); // Poll every 2 seconds
}

function updateBatchProgress(batchStatus) {
    const progressContent = document.getElementById('batchProgressContent');
    
    const completed = batchStatus.completed_tasks || 0;
    const failed = batchStatus.failed_tasks || 0;
    const processing = batchStatus.processing_tasks || 0;
    const pending = batchStatus.pending_tasks || 0;
    const total = batchStatus.total_tasks || 0;
    
    const progressPercent = total > 0 ? ((completed + failed) / total * 100).toFixed(1) : 0;
    
    let html = `
        <div class="batch-summary">
            <div class="batch-summary-item">
                <div class="batch-summary-label">Total Tasks</div>
                <div class="batch-summary-value">${total}</div>
            </div>
            <div class="batch-summary-item">
                <div class="batch-summary-label">Completed</div>
                <div class="batch-summary-value" style="color: var(--apple-green);">${completed}</div>
            </div>
            <div class="batch-summary-item">
                <div class="batch-summary-label">Processing</div>
                <div class="batch-summary-value" style="color: #ff9500;">${processing}</div>
            </div>
            <div class="batch-summary-item">
                <div class="batch-summary-label">Failed</div>
                <div class="batch-summary-value" style="color: #ff3b30;">${failed}</div>
            </div>
            <div class="batch-summary-item">
                <div class="batch-summary-label">Progress</div>
                <div class="batch-summary-value">${progressPercent}%</div>
            </div>
        </div>
        
        <div class="progress-bar" style="margin-bottom: 24px;">
            <div class="progress-bar-fill" style="width: ${progressPercent}%"></div>
        </div>
        
        ${batchStatus.total_duration ? `
            <div style="margin-bottom: 20px; padding: 16px; background: var(--apple-gray-1); border-radius: 12px;">
                <div style="font-size: 17px; font-weight: 500; color: var(--apple-gray-4); margin-bottom: 8px;">
                    Total Duration: ${formatDuration(batchStatus.total_duration)}
                </div>
                <div style="font-size: 14px; color: var(--apple-gray-3);">
                    Started: ${formatDate(batchStatus.started_at)}<br>
                    Completed: ${formatDate(batchStatus.completed_at)}
                </div>
            </div>
        ` : ''}
        
        <h4 style="margin-bottom: 16px; font-size: 19px; font-weight: 600;">Task Details</h4>
        <div style="max-height: 400px; overflow-y: auto;">
    `;
    
    if (batchStatus.tasks && batchStatus.tasks.length > 0) {
        html += batchStatus.tasks.map((task, index) => {
            const statusClass = task.status === 'completed' ? 'completed' : 
                               task.status === 'failed' ? 'failed' :
                               task.status === 'processing' || task.status === 'submitted' ? 'processing' : 'pending';
            
            return `
                <div class="task-item">
                    <div class="task-info">
                        <div style="font-weight: 500; margin-bottom: 4px;">${task.video_file}</div>
                        <div style="font-size: 14px; color: var(--apple-gray-3);">
                            ${task.task_id ? `Task ID: ${task.task_id.substring(0, 16)}...` : 'Pending...'}
                            ${task.duration ? ` • Duration: ${formatDuration(task.duration)}` : ''}
                            ${task.error ? ` • Error: ${task.error}` : ''}
                        </div>
                    </div>
                    <span class="task-status-badge ${statusClass}">${task.status}</span>
                </div>
            `;
        }).join('');
    } else {
        html += '<div class="loading">No tasks yet</div>';
    }
    
    html += '</div>';
    
    progressContent.innerHTML = html;
}

function formatDuration(seconds) {
    if (!seconds) return '0s';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins > 0) {
        return `${mins}m ${secs}s`;
    }
    return `${secs}s`;
}

async function clearStuckTasks(serverName) {
    if (!confirm(`Clear stuck tasks (pending/processing) on ${serverName}? This will mark them as stopped.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/server/${serverName}/tasks/mark-stopped`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                statuses: ['pending', 'processing']
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`✅ Successfully marked ${result.stopped_count || 0} tasks as stopped on ${serverName}\n\nStopped: ${result.stopped_count || 0}\nFailed: ${result.failed_count || 0}\nTotal checked: ${result.total_checked || 0}`);
            // Refresh server data
            refreshServerData(serverName);
        } else {
            alert(`❌ Failed to clear tasks: ${result.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error clearing stuck tasks:', error);
        alert(`❌ Error: ${error.message}`);
    }
}

// Export functions for use in HTML
window.refreshData = refreshData;
window.refreshTasks = refreshTasks;
window.refreshServerTasks = refreshServerTasks;
window.deleteTask = deleteTask;
window.onServerChange = onServerChange;
window.startBatchTranscription = startBatchTranscription;
window.clearStuckTasks = clearStuckTasks;
window.retryServerTask = retryServerTask;
window.cancelServerTask = cancelServerTask;
