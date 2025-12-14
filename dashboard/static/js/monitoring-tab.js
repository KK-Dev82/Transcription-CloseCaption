/**
 * Monitoring & Logs Tab JavaScript
 * Real-time monitoring, logs, and progress tracking
 */

let monitoringInterval = null;
let logsAutoScroll = true;
let progressTrackingIntervals = {};

// Current selected server for monitoring
let currentMonitoringServer = '4000-ada-sc';

// Start monitoring - only refresh when tab is active
let isMonitoringTabActive = false;

function startMonitoringTab() {
    isMonitoringTabActive = true;
    refreshMonitoringData();
    monitoringInterval = setInterval(() => {
        // Only refresh if tab is still active
        if (isMonitoringTabActive) {
            refreshMonitoringData();
        } else {
            stopMonitoringTab();
        }
    }, 5000); // Refresh every 5 seconds
}

function stopMonitoringTab() {
    isMonitoringTabActive = false;
    if (monitoringInterval) {
        clearInterval(monitoringInterval);
        monitoringInterval = null;
    }
    // Stop all progress tracking
    Object.values(progressTrackingIntervals).forEach(interval => {
        if (interval) clearInterval(interval);
    });
    progressTrackingIntervals = {};
}

// Server selection
function selectMonitoringServer(serverName) {
    currentMonitoringServer = serverName;
    
    // Update button states
    document.querySelectorAll('#tab-monitoring .server-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`monitoring-server-btn-${serverName}`).classList.add('active');
    
    // Update server name display
    document.getElementById('monitoring-server-name').textContent = serverName;
    
    // Refresh data for selected server
    refreshMonitoringData();
}

async function refreshMonitoringData() {
    await Promise.all([
        refreshRealTimeProgress(),
        refreshServerStatus(),
        refreshSystemLogs()
    ]);
}

// Real-time Progress Tracking
async function refreshRealTimeProgress() {
    const container = document.getElementById('realTimeProgress');
    if (!container) return;
    
    // Only show tasks from current selected server
    const serverName = currentMonitoringServer;
    
    try {
        const data = await dashboardAPI.getServerTasks(serverName, {
            limit: 50,
            status: null,
            timeout: 30  // เพิ่ม timeout จาก 10 เป็น 30 วินาที
        });
        
        if (data.error) {
            container.innerHTML = `<div class="error">Error: ${data.error}</div>`;
            return;
        }
        
        const allActiveTasks = [];
        
        if (data.tasks) {
            const activeTasks = data.tasks.filter(task => {
                const status = (task.status || 'unknown').toLowerCase();
                return status === 'processing' || status === 'pending' || status === 'transcribing';
            });
            
            activeTasks.forEach(task => {
                allActiveTasks.push({ ...task, server: serverName });
            });
        }
        
        if (allActiveTasks.length === 0) {
            container.innerHTML = '<div class="empty">No active tasks</div>';
            return;
        }
        
        container.innerHTML = allActiveTasks.map(task => {
            const progress = task.progress || 0;
            const stage = task.current_stage || task.current_stage_description || 'Processing';
            const taskId = task.task_id || task.id || 'N/A';
            const fileName = task.file_name || task.filename || 'N/A';
            
            return `
                <div class="progress-card">
                    <h4>${fileName.length > 30 ? fileName.substring(0, 30) + '...' : fileName}</h4>
                    <div class="task-id">${taskId.substring(0, 24)}...</div>
                    <div class="progress-bar-container" style="margin-top: 8px;">
                        <div class="progress-bar-fill" style="width: ${progress}%; background: ${progress < 50 ? '#ff9500' : progress < 80 ? '#0071e3' : '#34c759'};"></div>
                        <span class="progress-text">${progress}%</span>
                    </div>
                    <div class="stage-info">
                        <strong>Stage:</strong> ${stage}<br>
                        <strong>Server:</strong> ${task.server}<br>
                        <strong>Status:</strong> ${(task.status || 'unknown').toUpperCase()}
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error refreshing real-time progress:', error);
        container.innerHTML = `<div class="error">Error: ${error.message || 'Unknown error'}</div>`;
    }
}

// Server Status - Show only current selected server
async function refreshServerStatus() {
    const container = document.getElementById('serverStatusGrid');
    if (!container) return;
    
    const serverName = currentMonitoringServer;
    
    try {
        let summary, status, error = null;
        
        try {
            summary = await dashboardAPI.getServerSummary(serverName);
            status = await dashboardAPI.getServerStatus(serverName);
        } catch (err) {
            error = err.message;
        }
        
        if (error) {
            container.innerHTML = `
                <div class="status-card failed">
                    <h4>${serverName}</h4>
                    <div class="error">Error: ${error}</div>
                </div>
            `;
            return;
        }
        
        const total = summary?.total || 0;
        const completed = summary?.completed || 0;
        const processing = summary?.processing || 0;
        const pending = summary?.pending || 0;
        const failed = summary?.failed || 0;
        
        container.innerHTML = `
            <div class="status-card">
                <h4>${serverName}</h4>
                <div style="margin-top: 12px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span>Total:</span>
                        <strong>${total}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span>✅ Completed:</span>
                        <strong style="color: #34c759;">${completed}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span>⏳ Processing:</span>
                        <strong style="color: #ff9500;">${processing}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span>⏸️ Pending:</span>
                        <strong style="color: #0071e3;">${pending}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span>❌ Failed:</span>
                        <strong style="color: #ff3b30;">${failed}</strong>
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error refreshing server status:', error);
        container.innerHTML = `<div class="error">Error: ${error.message || 'Unknown error'}</div>`;
    }
}

// System Logs - Show logs from current selected server only
let logsBuffer = [];
const MAX_LOGS = 500;

async function refreshSystemLogs() {
    const container = document.getElementById('systemLogs');
    if (!container) return;
    
    const serverName = currentMonitoringServer;
    
    // In a real implementation, you would fetch logs from the server
    // For now, we'll simulate with task status updates from selected server
    try {
        const data = await dashboardAPI.getServerTasks(serverName, {
            limit: 20,
            status: null,
            timeout: 30  // เพิ่ม timeout จาก 5 เป็น 30 วินาที
        });
        
        if (data.tasks) {
            data.tasks.forEach(task => {
                const status = (task.status || 'unknown').toLowerCase();
                if (status === 'processing' || status === 'pending' || status === 'transcribing') {
                    const logEntry = {
                        timestamp: new Date().toISOString(),
                        server: serverName,
                        taskId: task.task_id || task.id,
                        status: status,
                        progress: task.progress || 0,
                        stage: task.current_stage || task.current_stage_description || 'Processing'
                    };
                    
                    // Avoid duplicates
                    const existing = logsBuffer.find(log => 
                        log.taskId === logEntry.taskId && 
                        log.status === logEntry.status &&
                        Math.abs(new Date(log.timestamp) - new Date(logEntry.timestamp)) < 5000
                    );
                    
                    if (!existing) {
                        logsBuffer.push(logEntry);
                        if (logsBuffer.length > MAX_LOGS) {
                            logsBuffer.shift();
                        }
                    }
                }
            });
        }
        
        // Render logs
        const logsHtml = logsBuffer.slice(-100).reverse().map(log => {
            const time = new Date(log.timestamp).toLocaleTimeString('th-TH');
            const logType = log.status === 'failed' ? 'error' : 
                           log.status === 'processing' ? 'info' : 'debug';
            
            return `
                <div class="log-entry ${logType}">
                    <span class="log-timestamp">[${time}]</span>
                    <strong>[${log.server}]</strong>
                    Task ${log.taskId.substring(0, 16)}... 
                    ${log.status.toUpperCase()} 
                    ${log.progress > 0 ? `(${log.progress}%)` : ''}
                    ${log.stage ? `- ${log.stage}` : ''}
                </div>
            `;
        }).join('');
        
        container.innerHTML = logsHtml || '<div class="log-entry info">No recent activity</div>';
        
        // Auto-scroll to bottom
        if (logsAutoScroll) {
            container.scrollTop = container.scrollHeight;
        }
    } catch (error) {
        console.error('Error refreshing system logs:', error);
    }
}

function clearLogs() {
    if (confirm('Clear all logs?')) {
        logsBuffer = [];
        const container = document.getElementById('systemLogs');
        if (container) {
            container.innerHTML = '<div class="log-entry info">[System] Logs cleared.</div>';
        }
    }
}

function toggleAutoScroll() {
    logsAutoScroll = !logsAutoScroll;
    const btn = document.getElementById('autoScrollBtn');
    if (btn) {
        btn.textContent = `📌 Auto-scroll: ${logsAutoScroll ? 'ON' : 'OFF'}`;
    }
}

// Progress tracking for individual tasks
function startProgressTracking(serverName, tasks) {
    // Stop existing tracking for this server
    if (progressTrackingIntervals[serverName]) {
        clearInterval(progressTrackingIntervals[serverName]);
    }
    
    if (tasks.length === 0) return;
    
    progressTrackingIntervals[serverName] = setInterval(async () => {
        try {
            for (const task of tasks) {
                const taskId = task.task_id || task.id;
                if (!taskId) continue;
                
                try {
                    const remoteAPI = new RemoteServerAPI(serverName);
                    const updatedTask = await remoteAPI.getTaskStatus(taskId);
                    
                    // Update progress in table if task row exists
                    const row = document.querySelector(`tr[data-task-id="${taskId}"]`);
                    if (row) {
                        const progress = updatedTask.progress || 0;
                        const status = (updatedTask.status || 'unknown').toLowerCase();
                        
                        // Update progress bar
                        const progressBar = row.querySelector('.progress-bar-fill');
                        const progressText = row.querySelector('.progress-text');
                        if (progressBar && progressText) {
                            progressBar.style.width = `${progress}%`;
                            progressText.textContent = `${progress}%`;
                            progressBar.style.background = progress < 50 ? '#ff9500' : progress < 80 ? '#0071e3' : '#34c759';
                        }
                        
                        // Update status badge
                        const statusBadge = row.querySelector('.status-badge');
                        if (statusBadge) {
                            statusBadge.className = `status-badge status-${status}`;
                            statusBadge.textContent = status.toUpperCase();
                        }
                        
                        // If completed, stop tracking
                        if (status === 'completed' || status === 'failed' || status === 'stopped') {
                            tasks = tasks.filter(t => (t.task_id || t.id) !== taskId);
                        }
                    }
                } catch (error) {
                    // Silent fail for individual task updates
                }
            }
            
            // Stop tracking if no more active tasks
            if (tasks.length === 0 && progressTrackingIntervals[serverName]) {
                clearInterval(progressTrackingIntervals[serverName]);
                delete progressTrackingIntervals[serverName];
            }
        } catch (error) {
            console.error(`Error tracking progress for ${serverName}:`, error);
        }
    }, 3000); // Update every 3 seconds
}

// Manual refresh
function manualRefreshMonitoring() {
    const btn = document.getElementById('refresh-monitoring-btn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳ Refreshing...';
    }
    
    refreshMonitoringData().finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '🔄 Refresh';
        }
    });
}

// Open in new window
function openMonitoringInNewWindow() {
    const newWindow = window.open(window.location.href, '_blank');
    if (newWindow) {
        newWindow.addEventListener('load', () => {
            // Switch to monitoring tab in new window
            setTimeout(() => {
                if (newWindow.switchTab) {
                    newWindow.switchTab('monitoring');
                }
            }, 500);
        });
    }
}

// Export functions
window.startMonitoringTab = startMonitoringTab;
window.stopMonitoringTab = stopMonitoringTab;
window.selectMonitoringServer = selectMonitoringServer;
window.refreshMonitoringData = refreshMonitoringData;
window.manualRefreshMonitoring = manualRefreshMonitoring;
window.openMonitoringInNewWindow = openMonitoringInNewWindow;
window.clearLogs = clearLogs;
window.toggleAutoScroll = toggleAutoScroll;
window.startProgressTracking = startProgressTracking;

