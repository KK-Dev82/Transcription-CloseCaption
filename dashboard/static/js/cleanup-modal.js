/**
 * Cleanup/Delete Modal JavaScript
 */

let currentDeleteServer = null;
let currentCleanupId = null;
let deleteProgressInterval = null;

function showDeleteOldTasksDialog(serverName) {
    if (!serverName) {
        console.error('showDeleteOldTasksDialog called without serverName');
        alert('Error: Server name is missing');
        return;
    }
    
    // Store server name
    currentDeleteServer = serverName;
    console.log('Opening delete dialog for server:', serverName, '| currentDeleteServer:', currentDeleteServer);
    
    const modal = document.getElementById('deleteOldTasksModal');
    if (!modal) {
        console.error('deleteOldTasksModal element not found');
        alert('Modal element not found. Please refresh the page.');
        return;
    }
    
    // Reset form values
    const deleteCompletedCheckbox = document.getElementById('deleteStatusCompleted');
    const deleteFailedCheckbox = document.getElementById('deleteStatusFailed');
    const deleteCancelledCheckbox = document.getElementById('deleteStatusCancelled');
    const daysSelect = document.getElementById('deleteDaysOption');
    
    if (deleteCompletedCheckbox) deleteCompletedCheckbox.checked = true;
    if (deleteFailedCheckbox) deleteFailedCheckbox.checked = true;
    if (deleteCancelledCheckbox) deleteCancelledCheckbox.checked = true;
    if (daysSelect) daysSelect.value = '7'; // Default to 7 days
    
    modal.style.display = 'flex';
}

function closeDeleteOldTasksDialog() {
    const modal = document.getElementById('deleteOldTasksModal');
    if (modal) {
        modal.style.display = 'none';
    }
    // Don't reset currentDeleteServer here - it might still be needed
    // currentDeleteServer = null;
}

function closeDeleteOldTasksModal() {
    closeDeleteOldTasksDialog();
}

async function confirmDeleteOldTasks() {
    // Store server name BEFORE closing modal (because closeDeleteOldTasksDialog might reset it)
    const serverName = currentDeleteServer;
    
    console.log('confirmDeleteOldTasks called | serverName:', serverName, '| currentDeleteServer:', currentDeleteServer);
    
    if (!serverName) {
        alert('❌ Error: Server name is missing. Please try again.');
        console.error('currentDeleteServer is null when confirmDeleteOldTasks called');
        return;
    }
    
    const daysOptionEl = document.getElementById('deleteDaysOption');
    const deleteCompletedEl = document.getElementById('deleteStatusCompleted');
    const deleteFailedEl = document.getElementById('deleteStatusFailed');
    const deleteCancelledEl = document.getElementById('deleteStatusCancelled');
    
    if (!daysOptionEl || !deleteCompletedEl || !deleteFailedEl || !deleteCancelledEl) {
        alert('❌ Error: Could not find form elements. Please refresh the page.');
        return;
    }
    
    const daysOption = daysOptionEl.value;
    const deleteCompleted = deleteCompletedEl.checked;
    const deleteFailed = deleteFailedEl.checked;
    const deleteCancelled = deleteCancelledEl.checked;
    
    if (!deleteCompleted && !deleteFailed && !deleteCancelled) {
        alert('Please select at least one status to delete');
        return;
    }
    
    const statuses = [];
    if (deleteCompleted) statuses.push('completed');
    if (deleteFailed) statuses.push('failed');
    if (deleteCancelled) {
        statuses.push('cancelled');
        statuses.push('stopped'); // Include both cancelled and stopped
    }
    
    const days = daysOption === 'all' ? null : parseInt(daysOption);
    
    console.log('Deleting old tasks:', { serverName, days, statuses });
    
    // Close modal (but don't reset currentDeleteServer yet - we'll use stored serverName)
    const modal = document.getElementById('deleteOldTasksModal');
    if (modal) {
        modal.style.display = 'none';
    }
    
    // Show progress bar
    showProgressBar();
    
    try {
        // Start deletion - use stored serverName, not currentDeleteServer
        const apiUrl = `/api/server/${serverName}/tasks/delete-old`;
        console.log('Calling API:', apiUrl);
        
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                days: days,
                statuses: statuses
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const result = await response.json();
        
        if (result.error) {
            hideProgressBar();
            alert(`❌ Error: ${result.error}`);
            return;
        }
        
        if (!result.cleanup_id) {
            hideProgressBar();
            alert(`❌ Error: No cleanup ID returned from server`);
            console.error('Server response:', result);
            return;
        }
        
        // Start polling progress
        currentCleanupId = result.cleanup_id;
        startDeleteProgressPolling();
        
    } catch (error) {
        hideProgressBar();
        console.error('Error deleting old tasks:', error);
        alert(`❌ Error: ${error.message || 'Failed to delete old tasks'}`);
    }
}

function showProgressBar() {
    const progressBar = document.getElementById('deleteProgressBar');
    if (!progressBar) {
        console.error('deleteProgressBar element not found');
        return;
    }
    progressBar.style.display = 'block';
    updateProgressBar(0, 0, 'Starting...');
}

function hideProgressBar() {
    const progressBar = document.getElementById('deleteProgressBar');
    progressBar.style.display = 'none';
    if (deleteProgressInterval) {
        clearInterval(deleteProgressInterval);
        deleteProgressInterval = null;
    }
    currentCleanupId = null;
}

function closeProgressBar() {
    hideProgressBar();
    // Reset server name when closing progress bar
    currentDeleteServer = null;
}

function startDeleteProgressPolling() {
    if (deleteProgressInterval) {
        clearInterval(deleteProgressInterval);
    }
    
    deleteProgressInterval = setInterval(async () => {
        if (!currentCleanupId) {
            clearInterval(deleteProgressInterval);
            return;
        }
        
        try {
            const response = await fetch(`/api/cleanup/${currentCleanupId}/progress`);
            const progress = await response.json();
            
            const total = progress.total || 0;
            const deleted = progress.deleted || 0;
            const failed = progress.failed || 0;
            const status = progress.status || 'unknown';
            const currentFile = progress.current_file || '';
            
            const percent = total > 0 ? Math.round((deleted / total) * 100) : 0;
            
            updateProgressBar(deleted, total, currentFile, percent, status);
            
            if (status === 'completed' || status === 'error') {
                clearInterval(deleteProgressInterval);
                deleteProgressInterval = null;
                
                if (status === 'completed') {
                    const completedServerName = currentDeleteServer; // Store before resetting
                    setTimeout(() => {
                        hideProgressBar();
                        alert(`✅ Deleted ${deleted} tasks successfully${failed > 0 ? `\n❌ Failed: ${failed}` : ''}`);
                        // Reset server name after completion
                        currentDeleteServer = null;
                        // Refresh overview if function exists
                        if (typeof refreshOverviewServer === 'function' && completedServerName) {
                            refreshOverviewServer(completedServerName);
                        }
                    }, 1000);
                } else {
                    hideProgressBar();
                    alert(`❌ Error: ${progress.error || 'Unknown error'}`);
                }
            }
        } catch (error) {
            console.error('Error polling delete progress:', error);
        }
    }, 500); // Poll every 500ms for real-time updates
}

function updateProgressBar(deleted, total, currentFile, percent = 0, status = 'processing') {
    const titleEl = document.getElementById('progressBarTitle');
    const fillEl = document.getElementById('progressBarFill');
    const textEl = document.getElementById('progressBarText');
    const percentEl = document.getElementById('progressBarPercent');
    const detailEl = document.getElementById('progressBarDetail');
    
    if (titleEl) {
        if (status === 'completed') {
            titleEl.textContent = '✅ Deletion completed';
        } else if (status === 'error') {
            titleEl.textContent = '❌ Deletion failed';
        } else {
            titleEl.textContent = 'Deleting old tasks...';
        }
    }
    
    if (fillEl) {
        fillEl.style.width = `${percent}%`;
    }
    
    if (textEl) {
        textEl.textContent = `${deleted} / ${total} files`;
    }
    
    if (percentEl) {
        percentEl.textContent = `${percent}%`;
    }
    
    if (detailEl) {
        if (status === 'processing' && currentFile) {
            detailEl.innerHTML = `<small>Deleting: ${currentFile.substring(0, 40)}...</small>`;
        } else if (status === 'completed') {
            detailEl.innerHTML = '<small style="color: var(--apple-green);">All tasks deleted successfully</small>';
        } else if (status === 'error') {
            detailEl.innerHTML = '<small style="color: #ff3b30;">An error occurred</small>';
        } else {
            detailEl.innerHTML = '<small>Preparing...</small>';
        }
    }
}

// Delete All Tasks (all statuses)
function showDeleteAllTasksDialog(serverName) {
    if (!serverName) {
        console.error('showDeleteAllTasksDialog called without serverName');
        alert('Error: Server name is missing');
        return;
    }
    
    if (!confirm(`⚠️ WARNING: This will delete ALL tasks on ${serverName} (all statuses: pending, processing, completed, failed, cancelled, stopped).\n\nThis action cannot be undone!\n\nAre you sure?`)) {
        return;
    }
    
    // Store server name
    currentDeleteServer = serverName;
    console.log('Opening delete ALL dialog for server:', serverName);
    
    // Show progress bar immediately
    showProgressBar();
    
    // Start deletion with all statuses
    confirmDeleteAllTasks(serverName);
}

async function confirmDeleteAllTasks(serverName) {
    console.log('confirmDeleteAllTasks called | serverName:', serverName);
    
    if (!serverName) {
        alert('❌ Error: Server name is missing.');
        hideProgressBar();
        return;
    }
    
    try {
        // Delete ALL tasks (all statuses, all ages)
        const apiUrl = `/api/server/${serverName}/tasks/delete-old`;
        console.log('Calling API to delete ALL tasks:', apiUrl);
        
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                days: null, // All ages
                statuses: ['pending', 'processing', 'completed', 'failed', 'cancelled', 'stopped'] // All statuses
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const result = await response.json();
        
        if (result.error) {
            hideProgressBar();
            alert(`❌ Error: ${result.error}`);
            return;
        }
        
        if (!result.cleanup_id) {
            hideProgressBar();
            alert(`❌ Error: No cleanup ID returned from server`);
            console.error('Server response:', result);
            return;
        }
        
        // Start polling progress
        currentCleanupId = result.cleanup_id;
        startDeleteProgressPolling();
        
    } catch (error) {
        hideProgressBar();
        console.error('Error deleting all tasks:', error);
        alert(`❌ Error: ${error.message || 'Failed to delete all tasks'}`);
    }
}

// Export functions
window.showDeleteOldTasksDialog = showDeleteOldTasksDialog;
window.showDeleteAllTasksDialog = showDeleteAllTasksDialog;
window.closeDeleteOldTasksDialog = closeDeleteOldTasksDialog;
window.closeDeleteOldTasksModal = closeDeleteOldTasksModal;
window.confirmDeleteOldTasks = confirmDeleteOldTasks;
window.closeProgressBar = closeProgressBar;

