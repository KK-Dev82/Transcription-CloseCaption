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
    if (!serverName) return;
    
    try {
        // Get status from Dashboard API (which proxies to remote server)
        let summary, status, systemInfo = null;
        let error = null;
        
        try {
            summary = await dashboardAPI.getServerSummary(serverName);
            status = await dashboardAPI.getServerStatus(serverName);
            
            // Try to get system info from Management API
            try {
                const managementAPI = getManagementAPI(serverName);
                systemInfo = await managementAPI.getSystemInfo();
            } catch (e) {
                console.debug('Management API not available, using basic status only');
            }
        } catch (err) {
            error = err.message;
        }
        
        if (error && !systemInfo) {
            container.innerHTML = `
                <div class="status-card failed">
                    <h4>${serverName}</h4>
                    <div class="error">Error: ${error}</div>
                </div>
            `;
            return;
        }
        
        let html = '';
        
        // Health Status with Restart Button
        if (status && status.health) {
            const healthStatus = status.health === 'healthy' ? 'success' : (status.health === 'unhealthy' ? 'error' : 'warning');
            html += `
                <div class="status-card ${healthStatus}">
                    <h4>Health Status</h4>
                    <p>${status.health || 'unknown'}</p>
                    <button class="btn-restart-service" onclick="restartTranscriptionService('${serverName}')" 
                            style="margin-top: 8px; padding: 6px 12px; background: #0071e3; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        🔄 Restart Service
                    </button>
                </div>
            `;
        } else {
            // Show health check even if status is not available
            html += `
                <div class="status-card warning">
                    <h4>Health Status</h4>
                    <p>Checking...</p>
                    <button class="btn-restart-service" onclick="restartTranscriptionService('${serverName}')" 
                            style="margin-top: 8px; padding: 6px 12px; background: #0071e3; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        🔄 Restart Service
                    </button>
                </div>
            `;
        }
        
        // System Info (from Management API)
        if (systemInfo && !systemInfo.error) {
            if (systemInfo.memory_usage) {
                const mem = systemInfo.memory_usage;
                const percent = mem.percent_used || ((mem.used_gb / mem.total_gb) * 100).toFixed(1);
                html += `
                    <div class="status-card ${percent > 90 ? 'error' : percent > 70 ? 'warning' : 'info'}">
                        <h4>Memory</h4>
                        <p>${percent}%</p>
                        <small>${mem.used_gb}GB / ${mem.total_gb}GB</small>
                    </div>
                `;
            }
            
            if (systemInfo.disk_usage) {
                const disk = systemInfo.disk_usage;
                const percent = disk.percent_used || ((disk.used_gb / disk.total_gb) * 100).toFixed(1);
                html += `
                    <div class="status-card ${percent > 90 ? 'error' : percent > 70 ? 'warning' : 'info'}">
                        <h4>Disk</h4>
                        <p>${percent}%</p>
                        <small>${disk.used_gb}GB / ${disk.total_gb}GB</small>
                    </div>
                `;
            }
            
            if (systemInfo.cpu_info) {
                const cpu = systemInfo.cpu_info;
                html += `
                    <div class="status-card info">
                        <h4>CPU</h4>
                        <p>${cpu.percent || 0}%</p>
                        <small>Cores: ${cpu.count || 'N/A'}</small>
                    </div>
                `;
            }
            
            if (systemInfo.gpu_info && systemInfo.gpu_info.length > 0) {
                systemInfo.gpu_info.forEach((gpu, idx) => {
                    const memPercent = ((gpu.memory_used_mb / gpu.memory_total_mb) * 100).toFixed(1);
                    html += `
                        <div class="status-card ${memPercent > 90 ? 'error' : memPercent > 70 ? 'warning' : 'success'}">
                            <h4>GPU ${idx + 1}</h4>
                            <p>${gpu.name || 'N/A'}</p>
                            <small>Memory: ${memPercent}% (${gpu.memory_used_mb}MB / ${gpu.memory_total_mb}MB)</small>
                            <small>Util: ${gpu.utilization_percent || 0}%</small>
                        </div>
                    `;
                });
            }
        }
        
        // Task Summary
        if (summary) {
            const total = summary?.total || 0;
            const completed = summary?.completed || 0;
            const processing = summary?.processing || 0;
            const pending = summary?.pending || 0;
            const failed = summary?.failed || 0;
            
            html += `
                <div class="status-card">
                    <h4>Tasks</h4>
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
        }
        
        // Worker Status
        if (status && status.worker && !status.worker.error) {
            html += `
                <div class="status-card ${status.worker.running ? 'success' : 'error'}">
                    <h4>Video Worker</h4>
                    <p>${status.worker.running ? 'Running' : 'Not Running'}</p>
                    ${status.worker.pid ? `<small>PID: ${status.worker.pid}</small>` : ''}
                </div>
            `;
        }
        
        // Queue Status
        if (status && status.queues && !status.queues.error) {
            const queueInfo = status.queues.queues || {};
            const queueNames = Object.keys(queueInfo);
            
            if (queueNames.length > 0) {
                html += `
                    <div class="status-card info">
                        <h4>Queues</h4>
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            ${queueNames.map(name => {
                                const queue = queueInfo[name];
                                return `<small>${name}: ${queue.message_count || 0} messages, ${queue.consumer_count || 0} consumers</small>`;
                            }).join('')}
                        </div>
                    </div>
                `;
            }
        }
        
        container.innerHTML = html || '<div class="status-card">No status data available</div>';
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
    if (!serverName) {
        container.innerHTML = '<div class="log-entry info">Select a server to view logs</div>';
        return;
    }
    
    try {
        // Try to use Management API to get real logs from remote server
        let logsData = null;
        try {
            const managementAPI = getManagementAPI(serverName);
            logsData = await managementAPI.getLogs('service', 50);
        } catch (e) {
            console.debug('Management API not available, falling back to task-based logs');
        }
        
        if (logsData && !logsData.error && logsData.lines && Array.isArray(logsData.lines)) {
            // Use real logs from Management API
            logsData.lines.forEach(logLine => {
                const logEntry = {
                    timestamp: new Date().toISOString(),
                    server: serverName,
                    message: logLine.trim(),
                    level: 'info'
                };
                
                // Determine log level from message
                if (logLine.includes('ERROR') || logLine.includes('error') || logLine.includes('❌')) {
                    logEntry.level = 'error';
                } else if (logLine.includes('WARNING') || logLine.includes('warning') || logLine.includes('⚠️')) {
                    logEntry.level = 'warning';
                }
                
                logsBuffer.push(logEntry);
                if (logsBuffer.length > MAX_LOGS) {
                    logsBuffer.shift();
                }
            });
        } else {
            // Fallback: Use task status updates
            const data = await dashboardAPI.getServerTasks(serverName, {
                limit: 20,
                status: null,
                timeout: 30
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
                            stage: task.current_stage || task.current_stage_description || 'Processing',
                            message: `Task ${(task.task_id || task.id).substring(0, 16)}... ${status.toUpperCase()} ${task.progress || 0}%`,
                            level: status === 'failed' ? 'error' : 'info'
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
        }
        
        // Render logs
        const logsHtml = logsBuffer.slice(-100).reverse().map(log => {
            const time = new Date(log.timestamp).toLocaleTimeString('th-TH');
            const logType = log.level || (log.status === 'failed' ? 'error' : 
                           log.status === 'processing' ? 'info' : 'debug');
            
            return `
                <div class="log-entry ${logType}">
                    <span class="log-timestamp">[${time}]</span>
                    <strong>[${log.server}]</strong>
                    ${log.message || `Task ${log.taskId?.substring(0, 16)}... ${log.status?.toUpperCase()} ${log.progress > 0 ? `(${log.progress}%)` : ''} ${log.stage ? `- ${log.stage}` : ''}`}
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
        container.innerHTML = `<div class="log-entry error">Error: ${error.message || 'Unknown error'}</div>`;
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
                    // Use Dashboard API proxy to avoid CORS issues
                    const updatedTask = await dashboardAPI.getTaskStatus(serverName, taskId);
                    
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

// Restart Service Function
async function restartTranscriptionService(serverName) {
    if (!confirm(`ต้องการ restart service บน ${serverName} ใช่หรือไม่?`)) {
        return;
    }
    
    const button = event.target;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = '⏳ Restarting...';
    
    try {
        const result = await dashboardAPI.restartService(serverName);
        if (result.success !== false) {
            alert(`✅ Service restart initiated on ${serverName}\n\nPlease wait 30-60 seconds for service to restart.`);
            // Refresh status after a delay
            setTimeout(() => {
                refreshServerStatus();
            }, 5000);
        } else {
            alert(`❌ Error: ${result.error || 'Failed to restart service'}`);
        }
    } catch (error) {
        console.error('Error restarting service:', error);
        alert(`❌ Error: ${error.message || 'Failed to restart service'}`);
    } finally {
        button.disabled = false;
        button.textContent = originalText;
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
window.restartTranscriptionService = restartTranscriptionService;

