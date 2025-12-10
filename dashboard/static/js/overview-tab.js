/**
 * Overview Tab JavaScript
 */

let overviewRefreshInterval = null;
const OVERVIEW_REFRESH_INTERVAL = 10000; // 10 seconds for overview

// Track displayed tasks per server for Load More
const displayedTasksCount = {
    '4000-ada': 20,
    '5080': 20
};

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

function formatDuration(seconds) {
    if (typeof seconds !== 'number' || isNaN(seconds) || seconds < 0) return 'N/A';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
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
            limit: 100, // Get up to 100 tasks
            status: null, // Don't filter on server
            timeout: 30 // 30s timeout
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
        
        // Reset displayed count when filter changes
        const currentFilter = filterEl ? filterEl.value : '';
        if (!window[`lastFilter_${serverName}`] || window[`lastFilter_${serverName}`] !== currentFilter) {
            displayedTasksCount[serverName] = 20;
            window[`lastFilter_${serverName}`] = currentFilter;
        }
        
        // Limit to displayed count
        const displayCount = displayedTasksCount[serverName] || 20;
        const displayedTasks = tasks.slice(0, displayCount);
        const hasMore = tasks.length > displayCount;
        
        container.innerHTML = displayedTasks.map(task => {
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
            
            // Get transcription text for completed tasks
            let textPreview = '';
            let viewTextButton = '';
            if (status === 'completed') {
                let fullText = task.full_text || task.corrected_text || task.original_text;
                
                // If no full_text, try to get from chunks
                if (!fullText && task.chunks && task.chunks.length > 0) {
                    const chunkTexts = task.chunks.filter(c => c.text).map(c => c.text);
                    if (chunkTexts.length > 0) {
                        fullText = chunkTexts.join(' ');
                    }
                }
                
                if (fullText && fullText.trim()) {
                    const preview = fullText.length > 150 ? fullText.substring(0, 150) + '...' : fullText;
                    textPreview = `<div style="font-size: 11px; color: var(--apple-gray-4); margin-top: 6px; padding: 6px; background: var(--apple-gray-1); border-radius: 4px; line-height: 1.4;">📝 ${preview}</div>`;
                    viewTextButton = `<button 
                        class="btn-view-text" 
                        onclick="viewTranscriptionText('${serverName}', '${taskId}')"
                        style="margin-top: 6px; padding: 4px 12px; font-size: 11px; background: var(--apple-blue); color: white; border: none; border-radius: 4px; cursor: pointer;"
                        title="View full text and chunks"
                    >🔍 View Text</button>`;
                }
            }
            
            // Show stop button for processing or pending tasks
            let stopButton = '';
            if (status === 'processing' || status === 'pending' || status === 'transcribing') {
                stopButton = `<button 
                    class="btn-stop-task" 
                    onclick="stopTask('${serverName}', '${taskId}')"
                    style="margin-top: 6px; padding: 4px 12px; font-size: 11px; background: var(--apple-red); color: white; border: none; border-radius: 4px; cursor: pointer;"
                    title="Stop this task"
                >⏹️ Stop</button>`;
            }
            
            return `
                <div class="log-item">
                    <div class="log-item-info">
                        <div class="log-item-id">${taskId.substring(0, 32)}...</div>
                        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 4px;">
                            <span class="log-item-status ${status}">${status}</span>
                            <span style="font-size: 12px; color: var(--apple-gray-3);">${progress}%</span>
                            ${stopButton}
                            ${viewTextButton}
                        </div>
                        <div style="font-size: 12px; color: var(--apple-gray-3); margin-top: 4px;">
                            ${fileName.length > 40 ? fileName.substring(0, 40) + '...' : fileName}${durationInfo}
                        </div>
                        <div class="log-item-time">${formatDate(updatedAt)}</div>
                        ${stepInfo !== 'N/A' ? `<div style="font-size: 11px; color: var(--apple-gray-3); margin-top: 4px;">Step: ${stepInfo}</div>` : ''}
                        ${textPreview}
                    </div>
                </div>
            `;
        }).join('') + (hasMore ? `
            <div style="text-align: center; margin-top: 16px; padding: 12px;">
                <button class="btn btn-secondary" onclick="loadMoreTasks('${serverName}')" style="padding: 8px 24px;">
                    📄 Load More (${tasks.length - displayCount} remaining)
                </button>
            </div>
        ` : '');
        
        if (displayedTasks.length === 0) {
            container.innerHTML = '<div class="empty">No tasks found</div>';
            return;
        }
    } catch (error) {
        console.error(`Error refreshing overview for ${serverName}:`, error);
        const container = document.getElementById(`logs-${serverName}`);
        if (container) {
            container.innerHTML = `<div class="error">Error: ${error.message || 'Unknown error'}</div>`;
        }
    }
}

async function clearPendingTasks(serverName) {
    if (!confirm(`Clear all pending tasks on ${serverName}?`)) {
        return;
    }
    
    try {
        const result = await dashboardAPI.markTasksStopped(serverName, ['pending', 'processing']);
        if (result.error) {
            alert(`Error: ${result.error}`);
        } else {
            alert(`✅ Cleared ${result.cleared_count || 0} tasks`);
            refreshOverviewServer(serverName);
        }
    } catch (error) {
        console.error('Error clearing tasks:', error);
        alert(`Error: ${error.message || 'Unknown error'}`);
    }
}

// Load More function
function loadMoreTasks(serverName) {
    displayedTasksCount[serverName] = (displayedTasksCount[serverName] || 20) + 20;
    refreshOverviewServer(serverName);
}

async function stopTask(serverName, taskId) {
    if (!confirm(`หยุด task ${taskId.substring(0, 16)}... บน ${serverName}?`)) {
        return;
    }
    
    try {
        const result = await dashboardAPI.stopTask(serverName, taskId);
        if (result.success) {
            alert(`✅ ${result.message || 'Task stopped successfully'}`);
            // Refresh the server's task list
            refreshOverviewServer(serverName);
        } else {
            alert(`❌ Error: ${result.error || 'Failed to stop task'}`);
        }
    } catch (error) {
        console.error('Error stopping task:', error);
        alert(`Error: ${error.message || 'Unknown error'}`);
    }
}

// Transcription Text Modal functions
let currentTranscriptionTask = null;
let currentTranscriptionServer = null;

async function viewTranscriptionText(serverName, taskId) {
    currentTranscriptionTask = taskId;
    currentTranscriptionServer = serverName;
    
    const modal = document.getElementById('transcriptionTextModal');
    const fulltextDiv = document.getElementById('transcription-fulltext');
    const chunksDiv = document.getElementById('transcription-chunks');
    
    // Show loading
    fulltextDiv.textContent = 'Loading...';
    chunksDiv.innerHTML = '<div class="loading">Loading chunks...</div>';
    modal.style.display = 'flex';
    
    // Reset to fulltext tab
    switchTranscriptionTab('fulltext');
    
    try {
        const remoteAPI = new RemoteServerAPI(serverName);
        const task = await remoteAPI.getTaskStatus(taskId);
        
        // Get full text
        let fullText = task.full_text || task.corrected_text || task.original_text;
        
        // If no full_text, construct from chunks
        if (!fullText && task.chunks && task.chunks.length > 0) {
            const chunkTexts = task.chunks.filter(c => c.text).map(c => c.text);
            if (chunkTexts.length > 0) {
                fullText = chunkTexts.join(' ');
            }
        }
        
        fulltextDiv.textContent = fullText || 'No text available';
        
        // Render chunks
        if (task.chunks && task.chunks.length > 0) {
            chunksDiv.innerHTML = task.chunks.map((chunk, index) => {
                const startTime = chunk.start_time !== undefined ? formatTime(chunk.start_time) : 'N/A';
                const endTime = chunk.end_time !== undefined ? formatTime(chunk.end_time) : 'N/A';
                return `
                    <div class="chunk-item">
                        <div class="chunk-item-header">
                            <span class="chunk-item-time">${startTime} - ${endTime}</span>
                            <span>Chunk #${index + 1}</span>
                        </div>
                        <div class="chunk-item-text">${chunk.text || ''}</div>
                    </div>
                `;
            }).join('');
        } else {
            chunksDiv.innerHTML = '<div style="text-align: center; padding: 24px; color: var(--apple-gray-3);">No chunks available</div>';
        }
    } catch (error) {
        console.error('Error loading transcription text:', error);
        fulltextDiv.textContent = `Error: ${error.message || 'Failed to load transcription'}`;
        chunksDiv.innerHTML = `<div style="color: #ff3b30;">Error loading chunks: ${error.message || 'Unknown error'}</div>`;
    }
}

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function switchTranscriptionTab(tab) {
    // Update tab buttons
    document.querySelectorAll('.modal-tab').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.modal-tab-content').forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none';
    });
    
    const activeContent = document.getElementById(`transcription-${tab}-content`);
    activeContent.classList.add('active');
    activeContent.style.display = 'block';
}

function closeTranscriptionTextModal() {
    const modal = document.getElementById('transcriptionTextModal');
    modal.style.display = 'none';
    currentTranscriptionTask = null;
    currentTranscriptionServer = null;
}

// Export functions
window.startOverviewRefresh = startOverviewRefresh;
window.stopOverviewRefresh = stopOverviewRefresh;
window.refreshOverviewData = refreshOverviewData;
window.refreshOverviewServer = refreshOverviewServer;
window.clearPendingTasks = clearPendingTasks;
window.loadMoreTasks = loadMoreTasks;
window.stopTask = stopTask;
window.viewTranscriptionText = viewTranscriptionText;
window.switchTranscriptionTab = switchTranscriptionTab;
window.closeTranscriptionTextModal = closeTranscriptionTextModal;
window.formatDate = formatDate;
window.formatDuration = formatDuration;
