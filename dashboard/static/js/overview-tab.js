/**
 * Overview Tab JavaScript
 */

// Current selected server
let currentOverviewServer = '4000-ada-sc';

// Pagination state per server
const paginationState = {
    '4000-ada-sc': { currentPage: 1, totalTasks: 0, tasksPerPage: 50, allTasks: [] },
    '4000-ada': { currentPage: 1, totalTasks: 0, tasksPerPage: 50, allTasks: [] },
    '5080': { currentPage: 1, totalTasks: 0, tasksPerPage: 50, allTasks: [] }
};

// Utility functions
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        const date = new Date(dateString);
        // Convert to UTC+7 (Thailand timezone) for display
        // toLocaleString with 'th-TH' should automatically use UTC+7
        return date.toLocaleString('th-TH', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZone: 'Asia/Bangkok'  // Explicitly set timezone to UTC+7
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

// Overview Tab Functions - No auto-refresh, manual refresh only
function startOverviewRefresh() {
    // Disabled - use manual refresh instead
}

function stopOverviewRefresh() {
    // Disabled - no auto-refresh
}

// Server selection
function selectOverviewServer(serverName) {
    currentOverviewServer = serverName;
    
    // Update button states
    document.querySelectorAll('.server-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`server-btn-${serverName}`).classList.add('active');
    
    // Update server name display
    document.getElementById('overview-server-name').textContent = serverName;
    
    // Reset to page 1 when switching servers
    paginationState[serverName].currentPage = 1;
    
    // Refresh the selected server
    refreshOverviewServer(serverName);
}

// Manual refresh
function manualRefreshOverview() {
    const btn = document.getElementById('refresh-overview-btn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳ Refreshing...';
    }
    
    // Clear cache to force reload
    paginationState[currentOverviewServer].allTasks = [];
    paginationState[currentOverviewServer].currentPage = 1;
    
    refreshOverviewServer(currentOverviewServer).finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '🔄 Refresh';
        }
    });
}

// Filter change handler
function onOverviewFilterChange() {
    // Reset pagination when filter changes
    paginationState[currentOverviewServer].currentPage = 1;
    paginationState[currentOverviewServer].allTasks = []; // Clear cache to reload
    refreshOverviewServer(currentOverviewServer);
}

// Helper functions for current server
function clearPendingTasksCurrent() {
    clearPendingTasks(currentOverviewServer);
}

function showDeleteOldTasksDialogCurrent() {
    showDeleteOldTasksDialog(currentOverviewServer);
}

function showDeleteAllTasksDialogCurrent() {
    showDeleteAllTasksDialog(currentOverviewServer);
}

async function refreshOverviewServer(serverName, page = null) {
    const container = document.getElementById('overview-tasks-container');
    if (!container) return;
    
    // Only refresh if this is the current selected server
    if (serverName !== currentOverviewServer) return;
    
    // Show loader
    container.innerHTML = `
        <div class="table-loader">
            <div class="loader-spinner"></div>
            <div class="loader-text">Loading tasks...</div>
        </div>
    `;
    
    try {
        const filterEl = document.getElementById('overview-status-filter');
        const statusFilter = filterEl ? filterEl.value : '';
        
        // Reset pagination when filter changes
        const currentFilter = filterEl ? filterEl.value : '';
        if (!window[`lastFilter_${serverName}`] || window[`lastFilter_${serverName}`] !== currentFilter) {
            paginationState[serverName].currentPage = 1;
            paginationState[serverName].allTasks = [];
            window[`lastFilter_${serverName}`] = currentFilter;
        }
        
        // Update page if provided
        if (page !== null) {
            paginationState[serverName].currentPage = page;
        }
        
        const state = paginationState[serverName];
        
        // Fetch 1000 tasks if not cached or filter changed
        if (state.allTasks.length === 0) {
            const data = await dashboardAPI.getServerTasks(serverName, {
                limit: 1000, // Load 1000 tasks for pagination
                status: null, // Don't filter on server
                timeout: 60
            });

            if (data.error) {
                container.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                return;
            }

            state.allTasks = data.tasks || [];
        }
        
        let tasks = [...state.allTasks];
        
        // Client-side filtering
        if (statusFilter) {
            tasks = tasks.filter(task => {
                const taskStatus = (task.status || 'unknown').toLowerCase();
                return taskStatus === statusFilter.toLowerCase();
            });
        }
        
        // Update total tasks after filtering
        state.totalTasks = tasks.length;
        
        // Calculate pagination
        const totalPages = Math.ceil(state.totalTasks / state.tasksPerPage);
        const startIndex = (state.currentPage - 1) * state.tasksPerPage;
        const endIndex = startIndex + state.tasksPerPage;
        const displayedTasks = tasks.slice(startIndex, endIndex);
        
        // Calculate row numbers (continuous across pages)
        const startRowNumber = startIndex + 1;
        
        // Render as Table (Admin Dashboard Style)
        container.innerHTML = `
            <div class="admin-table-container">
                <table class="admin-table">
                    <thead>
                        <tr>
                            <th style="width: 60px;">#</th>
                            <th style="width: 200px;">Task ID</th>
                            <th style="width: 100px;">Status</th>
                            <th style="width: 80px;">Progress</th>
                            <th style="width: 250px;">File Name</th>
                            <th style="width: 120px;">Duration</th>
                            <th style="width: 150px;">Created</th>
                            <th style="width: 150px;">Updated</th>
                            <th style="width: 120px;">Processing Time</th>
                            <th style="width: 150px;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${displayedTasks.map((task, index) => {
            // Calculate row number (continuous across pages)
            const rowNumber = startRowNumber + index;
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
            
            // Calculate processing time - แสดงรายละเอียด audio extraction และ transcription time
            let processingTimeStr = 'N/A';
            if (status === 'completed') {
                const audioTime = task.audio_extraction_time || task.audio_extraction_time === 0 ? parseFloat(task.audio_extraction_time) : null;
                const transcribeTime = task.transcription_time || task.transcription_time === 0 ? parseFloat(task.transcription_time) : null;
                const totalTime = task.processing_time || task.time_used || (task.processing_time === 0 ? 0 : null);
                
                // สร้างรายละเอียดเวลา
                const timeParts = [];
                if (audioTime !== null && !isNaN(audioTime) && audioTime > 0) {
                    timeParts.push(`🎵 ${formatTimeDuration(audioTime)}`);
                }
                if (transcribeTime !== null && !isNaN(transcribeTime) && transcribeTime > 0) {
                    timeParts.push(`🎤 ${formatTimeDuration(transcribeTime)}`);
                }
                if (timeParts.length > 0) {
                    processingTimeStr = timeParts.join(' + ');
                } else if (totalTime !== null && !isNaN(totalTime) && totalTime > 0) {
                    processingTimeStr = `⏱️ ${formatTimeDuration(totalTime)}`;
                }
            } else if (status === 'processing' || status === 'pending') {
                processingTimeStr = '<span class="processing-indicator">⏳ Processing...</span>';
            }
            
            // Status badge
            const statusBadge = `<span class="status-badge status-${status}">${status.toUpperCase()}</span>`;
            
            // Progress bar
            const progressBar = status === 'processing' || status === 'pending' 
                ? `<div class="progress-bar-container">
                     <div class="progress-bar-fill" style="width: ${progress}%; background: ${progress < 50 ? '#ff9500' : progress < 80 ? '#0071e3' : '#34c759'};"></div>
                     <span class="progress-text">${progress}%</span>
                   </div>`
                : progress > 0 ? `${progress}%` : 'N/A';
            
            // Actions column
            const actions = [];
            if (status === 'completed' && (task.full_text || task.corrected_text || task.original_text || (task.chunks && task.chunks.length > 0))) {
                actions.push(`<button class="btn-action btn-view" onclick="viewTranscriptionText('${serverName}', '${taskId}')" title="View transcription">🔍 View</button>`);
            }
            if (status === 'processing' || status === 'pending' || status === 'transcribing') {
                actions.push(`<button class="btn-action btn-stop" onclick="stopTask('${serverName}', '${taskId}')" title="Stop task">⏹️ Stop</button>`);
            }
            // Add Check Task button for stuck tasks
            if (status === 'pending' || status === 'processing' || status === 'transcribing') {
                actions.push(`<button class="btn-action btn-check" onclick="checkTaskInQueue('${serverName}', '${taskId}')" title="Check task status">🔍 Check</button>`);
            }
            
            const actionsHtml = actions.length > 0 ? actions.join(' ') : '-';
            
            return `
                <tr class="task-row task-${status}" data-task-id="${taskId}">
                    <td class="row-number-cell">
                        <strong>${rowNumber}</strong>
                    </td>
                    <td>
                        <div class="task-id-cell" title="${taskId}">
                            <code>${taskId.substring(0, 16)}...</code>
                        </div>
                    </td>
                    <td>${statusBadge}</td>
                    <td>${progressBar}</td>
                    <td>
                        <div class="file-name-cell" title="${fileName}">
                            ${fileName.length > 30 ? fileName.substring(0, 30) + '...' : fileName}
                            ${durationInfo ? `<span class="duration-badge">${durationInfo.replace(/[()]/g, '')}</span>` : ''}
                        </div>
                    </td>
                    <td>${durationInfo || 'N/A'}</td>
                    <td class="time-cell">${formatDate(task.created_at || created_at)}</td>
                    <td class="time-cell">${formatDate(updatedAt)}</td>
                    <td class="time-cell">${processingTimeStr}</td>
                    <td class="actions-cell">${actionsHtml}</td>
                </tr>
            `;
        }).join('')}
                    </tbody>
                </table>
            </div>
            ${renderPagination(serverName, state.currentPage, totalPages, state.totalTasks)}
        `;
        
        if (displayedTasks.length === 0) {
            container.innerHTML = '<div class="empty">No tasks found</div>';
            return;
        }
        
        // Start real-time progress tracking for processing tasks
        if (typeof startProgressTracking === 'function') {
            startProgressTracking(serverName, displayedTasks.filter(t => 
                ['processing', 'pending', 'transcribing'].includes((t.status || 'unknown').toLowerCase())
            ));
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

// Pagination functions
function renderPagination(serverName, currentPage, totalPages, totalTasks) {
    if (totalPages <= 1) return '';
    
    const tasksPerPage = paginationState[serverName].tasksPerPage;
    const startTask = (currentPage - 1) * tasksPerPage + 1;
    const endTask = Math.min(currentPage * tasksPerPage, totalTasks);
    
    // Calculate page numbers to show
    const maxPagesToShow = 7;
    let startPage = Math.max(1, currentPage - Math.floor(maxPagesToShow / 2));
    let endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);
    
    if (endPage - startPage < maxPagesToShow - 1) {
        startPage = Math.max(1, endPage - maxPagesToShow + 1);
    }
    
    const pageButtons = [];
    
    // First page
    if (startPage > 1) {
        pageButtons.push(`<button class="pagination-btn" onclick="goToPage('${serverName}', 1)">1</button>`);
        if (startPage > 2) {
            pageButtons.push(`<span class="pagination-ellipsis">...</span>`);
        }
    }
    
    // Page numbers
    for (let i = startPage; i <= endPage; i++) {
        pageButtons.push(
            `<button class="pagination-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage('${serverName}', ${i})">${i}</button>`
        );
    }
    
    // Last page
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            pageButtons.push(`<span class="pagination-ellipsis">...</span>`);
        }
        pageButtons.push(`<button class="pagination-btn" onclick="goToPage('${serverName}', ${totalPages})">${totalPages}</button>`);
    }
    
    return `
        <div class="pagination-container">
            <div class="pagination-info">
                Showing ${startTask}-${endTask} of ${totalTasks} tasks
            </div>
            <div class="pagination-controls">
                <button class="pagination-btn" onclick="goToPage('${serverName}', ${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
                    ← Previous
                </button>
                ${pageButtons.join('')}
                <button class="pagination-btn" onclick="goToPage('${serverName}', ${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
                    Next →
                </button>
            </div>
        </div>
    `;
}

function goToPage(serverName, page) {
    const state = paginationState[serverName];
    const totalPages = Math.ceil(state.totalTasks / state.tasksPerPage);
    
    if (page < 1 || page > totalPages) return;
    
    refreshOverviewServer(serverName, page);
    
    // Scroll to top of table
    const container = document.getElementById(`logs-${serverName}`);
    if (container) {
        container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

async function stopTask(serverName, taskId) {
    if (!confirm(`หยุด task ${taskId.substring(0, 16)}... บน ${serverName}?`)) {
        return;
    }
    
    try {
        const result = await dashboardAPI.stopTask(serverName, taskId);
        if (result && result.success) {
            alert(`✅ ${result.message || 'Task stopped successfully'}`);
            // Refresh the server's task list
            refreshOverviewServer(serverName);
        } else {
            // Handle both error formats: result.error or result.message
            const errorMsg = result?.error || result?.message || 'Failed to stop task';
            alert(`⚠️ ${errorMsg}${result?.note ? '\n\n' + result.note : ''}`);
            // Still refresh to show current status
            refreshOverviewServer(serverName);
        }
    } catch (error) {
        console.error('Error stopping task:', error);
        alert(`❌ Error: ${error.message || 'Unknown error'}\n\nTask may already be completed or the server may not support stopping tasks.`);
        // Still refresh to show current status
        refreshOverviewServer(serverName);
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
        // Use Dashboard API proxy to avoid CORS issues
        const task = await dashboardAPI.getTaskStatus(serverName, taskId);
        
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
                const chunkPath = chunk.chunk_path;
                const hasAudio = chunkPath && chunkPath.trim() !== '';
                
                // Build audio player HTML if chunk_path exists
                let audioPlayerHtml = '';
                if (hasAudio) {
                    const audioUrl = `/api/server/${serverName}/chunk-audio/${taskId}/${index}`;
                    audioPlayerHtml = `
                        <div class="chunk-audio-player" style="margin-top: 8px; padding: 8px; background: var(--apple-gray-1); border-radius: 4px;">
                            <audio controls style="width: 100%; max-width: 500px;" preload="metadata">
                                <source src="${audioUrl}" type="audio/wav">
                                Your browser does not support the audio element.
                            </audio>
                        </div>
                    `;
                }
                
                return `
                    <div class="chunk-item">
                        <div class="chunk-item-header">
                            <span class="chunk-item-time">${startTime} - ${endTime}</span>
                            <span>Chunk #${index + 1}</span>
                        </div>
                        ${audioPlayerHtml}
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
window.selectOverviewServer = selectOverviewServer;
window.manualRefreshOverview = manualRefreshOverview;
window.onOverviewFilterChange = onOverviewFilterChange;
window.clearPendingTasksCurrent = clearPendingTasksCurrent;
window.showDeleteOldTasksDialogCurrent = showDeleteOldTasksDialogCurrent;
window.showDeleteAllTasksDialogCurrent = showDeleteAllTasksDialogCurrent;
window.refreshOverviewServer = refreshOverviewServer;
window.clearPendingTasks = clearPendingTasks;
window.goToPage = goToPage;
window.stopTask = stopTask;
window.viewTranscriptionText = viewTranscriptionText;
window.switchTranscriptionTab = switchTranscriptionTab;
window.closeTranscriptionTextModal = closeTranscriptionTextModal;
window.formatDate = formatDate;
window.formatDuration = formatDuration;
