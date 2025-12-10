/**
 * Overview Tab JavaScript
 */

let overviewRefreshInterval = null;
const OVERVIEW_REFRESH_INTERVAL = 10000; // 10 seconds for overview

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

// Overview Tab Functions
function startOverviewRefresh() {
    stopOverviewRefresh();
    refreshOverviewData();
    overviewRefreshInterval = setInterval(() => {
        refreshOverviewData();
    }, OVERVIEW_REFRESH_INTERVAL);
}

function stopOverviewRefresh() {
    if (overviewRefreshInterval) {
        clearInterval(overviewRefreshInterval);
        overviewRefreshInterval = null;
    }
}

async function refreshOverviewData() {
    await Promise.all([
        refreshOverviewServer('4000-ada'),
        refreshOverviewServer('5080')
    ]);
}

async function refreshOverviewServer(serverName) {
    try {
        const filterEl = document.getElementById(`filter-${serverName}`);
        const statusFilter = filterEl ? filterEl.value : '';
        
        // Always fetch all tasks first, then filter client-side if needed
        const data = await dashboardAPI.getServerTasks(serverName, {
            limit: 100, // Get more tasks to filter from
            status: null, // Don't filter on server
            timeout: 10
        });

        const container = document.getElementById(`logs-${serverName}`);
        if (!container) return;

        if (data.error) {
            container.innerHTML = `<div class="error">Error: ${data.error}</div>`;
            return;
        }

        let tasks = data.tasks || [];
        
        // Client-side filtering
        if (statusFilter) {
            tasks = tasks.filter(task => {
                const taskStatus = (task.status || 'unknown').toLowerCase();
                return taskStatus === statusFilter.toLowerCase();
            });
        }
        
        // Limit to 20 after filtering
        tasks = tasks.slice(0, 20);
        
        if (tasks.length === 0) {
            container.innerHTML = '<div class="loading">No tasks found</div>';
            return;
        }

        container.innerHTML = tasks.map(task => {
            const taskId = task.task_id || task.id || 'N/A';
            const status = (task.status || 'unknown').toLowerCase();
            const updatedAt = task.updated_at || task.created_at || '';
            const progress = task.progress || 0;
            const fileName = task.file_name || task.filename || 'N/A';
            const stepInfo = task.current_stage || 'N/A';
            
            // Get video duration (check multiple possible fields)
            let durationInfo = '';
            let duration = null;
            
            if (task.total_duration) {
                duration = parseFloat(task.total_duration);
            } else if (task.video_duration) {
                duration = parseFloat(task.video_duration);
            } else if (task.duration) {
                duration = parseFloat(task.duration);
            } else if (task.duration_seconds) {
                duration = parseFloat(task.duration_seconds);
            }
            
            if (duration && !isNaN(duration) && duration > 0) {
                const minutes = Math.floor(duration / 60);
                const seconds = Math.floor(duration % 60);
                durationInfo = ` (${minutes}:${seconds.toString().padStart(2, '0')})`;
            }
            
            return `
                <div class="log-item">
                    <div class="log-item-info">
                        <div class="log-item-id">${taskId.substring(0, 32)}...</div>
                        <div>
                            <span class="log-item-status ${status}">${status}</span>
                            <span style="margin-left: 8px; font-size: 12px; color: var(--apple-gray-3);">${progress}%</span>
                        </div>
                        <div style="font-size: 12px; color: var(--apple-gray-3); margin-top: 4px;">
                            ${fileName.length > 40 ? fileName.substring(0, 40) + '...' : fileName}${durationInfo}
                        </div>
                        <div class="log-item-time">${formatDate(updatedAt)}</div>
                        ${stepInfo !== 'N/A' ? `<div style="font-size: 11px; color: var(--apple-gray-3); margin-top: 4px;">Step: ${stepInfo}</div>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error(`Error refreshing overview for ${serverName}:`, error);
        const container = document.getElementById(`logs-${serverName}`);
        if (container) {
            container.innerHTML = `<div class="error">Error: ${error.message}</div>`;
        }
    }
}

async function clearPendingTasks(serverName) {
    if (!confirm(`Clear all pending tasks on ${serverName}? This will mark them as stopped.`)) {
        return;
    }

    try {
        const result = await dashboardAPI.markTasksStopped(serverName, ['pending']);
        if (result.success) {
            alert(`✅ Cleared ${result.stopped_count || 0} pending tasks`);
            refreshOverviewServer(serverName);
        } else {
            alert(`❌ Failed: ${result.message || 'Unknown error'}`);
        }
    } catch (error) {
        alert(`❌ Error: ${error.message}`);
    }
}

// Export functions
window.clearPendingTasks = clearPendingTasks;
window.refreshOverviewServer = refreshOverviewServer;
window.refreshOverviewData = refreshOverviewData;
window.startOverviewRefresh = startOverviewRefresh;
window.stopOverviewRefresh = stopOverviewRefresh;

