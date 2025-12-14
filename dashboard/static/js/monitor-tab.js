/**
 * Monitor Tab JavaScript
 * สำหรับติดตามและวิเคราะห์ Transcription Jobs
 */

let monitorRefreshInterval = null;
let monitorTaskIds = [];
let monitorStartTime = null;
let monitorAnalysis = null;

const MONITOR_REFRESH_INTERVAL = 10000; // 10 seconds

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

function onMonitorServerChange() {
    updateMonitorStartButton();
}

function onMonitorMethodChange() {
    const method = document.getElementById('monitorMethod').value;
    
    // Hide all input groups
    document.getElementById('monitorBatchIdGroup').style.display = 'none';
    document.getElementById('monitorTaskIdsGroup').style.display = 'none';
    document.getElementById('monitorCountGroup').style.display = 'none';
    
    // Show relevant input group
    if (method === 'batch-id') {
        document.getElementById('monitorBatchIdGroup').style.display = 'block';
    } else if (method === 'task-ids') {
        document.getElementById('monitorTaskIdsGroup').style.display = 'block';
    } else if (method === 'count') {
        document.getElementById('monitorCountGroup').style.display = 'block';
    }
    
    updateMonitorStartButton();
}

function updateMonitorStartButton() {
    const serverName = document.getElementById('monitorServer').value;
    const method = document.getElementById('monitorMethod').value;
    const startBtn = document.getElementById('startMonitorBtn');
    
    let isValid = false;
    
    if (serverName) {
        if (method === 'batch-id') {
            const batchId = document.getElementById('monitorBatchId').value.trim();
            isValid = batchId.length > 0;
        } else if (method === 'task-ids') {
            const taskIds = document.getElementById('monitorTaskIds').value.trim();
            isValid = taskIds.length > 0;
        } else if (method === 'count') {
            const count = parseInt(document.getElementById('monitorCount').value);
            isValid = count >= 1 && count <= 100;
        }
    }
    
    startBtn.disabled = !isValid;
}

async function startMonitoring() {
    const serverName = document.getElementById('monitorServer').value;
    const method = document.getElementById('monitorMethod').value;
    const interval = parseInt(document.getElementById('monitorInterval').value) || 10;
    
    if (!serverName) {
        alert('Please select a server');
        return;
    }
    
    let taskIds = [];
    
    try {
        if (method === 'batch-id') {
            const batchId = document.getElementById('monitorBatchId').value.trim();
            if (!batchId) {
                alert('Please enter batch ID');
                return;
            }
            
            // Get task IDs from batch
            const batchStatus = await dashboardAPI.getBatchStatus(batchId);
            if (batchStatus && batchStatus.task_ids && batchStatus.task_ids.length > 0) {
                taskIds = batchStatus.task_ids;
            } else {
                alert('Batch not found or no tasks in batch');
                return;
            }
        } else if (method === 'task-ids') {
            const taskIdsInput = document.getElementById('monitorTaskIds').value.trim();
            if (!taskIdsInput) {
                alert('Please enter task IDs');
                return;
            }
            
            // Parse task IDs (comma or line separated)
            taskIds = taskIdsInput
                .split(/[,\n]/)
                .map(id => id.trim())
                .filter(id => id.length > 0);
        } else if (method === 'count') {
            const count = parseInt(document.getElementById('monitorCount').value);
            if (count < 1 || count > 100) {
                alert('Count must be between 1 and 100');
                return;
            }
            
            // Get latest tasks
            const data = await dashboardAPI.getServerTasks(serverName, { limit: count });
            if (data.tasks && data.tasks.length > 0) {
                taskIds = data.tasks
                    .map(task => task.task_id || task.id)
                    .filter(id => id);
            } else {
                alert('No tasks found');
                return;
            }
        }
        
        if (taskIds.length === 0) {
            alert('No tasks to monitor');
            return;
        }
        
        monitorTaskIds = taskIds;
        monitorStartTime = new Date();
        
        // Show status section
        document.getElementById('monitorStatusSection').style.display = 'block';
        document.getElementById('monitorResultsSection').style.display = 'none';
        
        // Start monitoring
        startMonitorRefresh(serverName, interval);
        
        // Scroll to status
        document.getElementById('monitorStatusSection').scrollIntoView({ behavior: 'smooth' });
        
    } catch (error) {
        console.error('Error starting monitoring:', error);
        alert(`Error: ${error.message || 'Failed to start monitoring'}`);
    }
}

function startMonitorRefresh(serverName, interval) {
    stopMonitorRefresh();
    
    // Initial refresh
    refreshMonitorStatus(serverName);
    
    // Set interval
    monitorRefreshInterval = setInterval(() => {
        refreshMonitorStatus(serverName);
    }, interval * 1000);
}

function stopMonitorRefresh() {
    if (monitorRefreshInterval) {
        clearInterval(monitorRefreshInterval);
        monitorRefreshInterval = null;
    }
}

function stopMonitoring() {
    stopMonitorRefresh();
    document.getElementById('stopMonitorBtn').disabled = true;
    document.getElementById('stopMonitorBtn').textContent = '⏹️ Stopped';
}

async function refreshMonitorStatus(serverName) {
    if (monitorTaskIds.length === 0) return;
    
    try {
        // Use Dashboard API proxy to avoid CORS issues
        // Fetch all task statuses
        const tasks = await Promise.all(
            monitorTaskIds.map(async (taskId) => {
                try {
                    return await dashboardAPI.getTaskStatus(serverName, taskId);
                } catch (error) {
                    console.error(`Error fetching task ${taskId}:`, error);
                    return { task_id: taskId, status: 'unknown' };
                }
            })
        );
        
        const validTasks = tasks.filter(t => t !== null);
        
        // Update progress
        updateMonitorProgress(validTasks);
        
        // Check if all finished
        const allFinished = validTasks.every(task => {
            const status = (task.status || 'unknown').toLowerCase();
            return status === 'completed' || status === 'failed' || status === 'stopped';
        });
        
        if (allFinished && validTasks.length > 0) {
            stopMonitorRefresh();
            document.getElementById('stopMonitorBtn').disabled = true;
            document.getElementById('stopMonitorBtn').textContent = '✅ Completed';
            
            // Analyze results
            analyzeResults(validTasks, serverName);
        }
        
    } catch (error) {
        console.error('Error refreshing monitor status:', error);
    }
}

function updateMonitorProgress(tasks) {
    const progressDiv = document.getElementById('monitorProgress');
    if (!progressDiv) return;
    
    const total = monitorTaskIds.length;
    const completed = tasks.filter(t => (t.status || '').toLowerCase() === 'completed').length;
    const failed = tasks.filter(t => (t.status || '').toLowerCase() === 'failed').length;
    const processing = tasks.filter(t => (t.status || '').toLowerCase() === 'processing').length;
    const pending = tasks.filter(t => (t.status || '').toLowerCase() === 'pending').length;
    const finished = completed + failed;
    
    const elapsed = monitorStartTime ? Math.floor((new Date() - monitorStartTime) / 1000) : 0;
    const elapsedStr = formatTimeDuration(elapsed);
    
    const progressPercent = total > 0 ? Math.round((finished / total) * 100) : 0;
    
    progressDiv.innerHTML = `
        <div class="monitor-progress-stats">
            <div class="progress-stat">
                <div class="progress-stat-value">${finished}/${total}</div>
                <div class="progress-stat-label">Finished</div>
            </div>
            <div class="progress-stat">
                <div class="progress-stat-value" style="color: var(--apple-green);">${completed}</div>
                <div class="progress-stat-label">Completed</div>
            </div>
            <div class="progress-stat">
                <div class="progress-stat-value" style="color: #ff3b30;">${failed}</div>
                <div class="progress-stat-label">Failed</div>
            </div>
            <div class="progress-stat">
                <div class="progress-stat-value" style="color: #ff9500;">${processing}</div>
                <div class="progress-stat-label">Processing</div>
            </div>
            <div class="progress-stat">
                <div class="progress-stat-value" style="color: #007aff;">${pending}</div>
                <div class="progress-stat-label">Pending</div>
            </div>
            <div class="progress-stat">
                <div class="progress-stat-value">${elapsedStr}</div>
                <div class="progress-stat-label">Elapsed</div>
            </div>
        </div>
        <div class="progress-bar" style="margin-top: 16px;">
            <div class="progress-bar-fill" style="width: ${progressPercent}%"></div>
        </div>
        <div style="text-align: center; margin-top: 8px; color: var(--apple-gray-3);">
            ${progressPercent}% Complete
        </div>
    `;
}

function analyzeResults(tasks, serverName) {
    const analysis = {
        total_tasks: tasks.length,
        completed: 0,
        failed: 0,
        processing_times: [],
        audio_extraction_times: [],
        transcription_times: [],
        total_durations: [],
        text_lengths: [],
        chunk_counts: [],
        thai_text_quality: {
            has_thai: 0,
            total_chars: 0,
            thai_chars: 0
        },
        errors: []
    };
    
    tasks.forEach(task => {
        const status = (task.status || 'unknown').toLowerCase();
        
        if (status === 'completed') {
            analysis.completed++;
            
            // Processing times
            if (task.audio_extraction_time) {
                analysis.audio_extraction_times.push(parseFloat(task.audio_extraction_time));
            }
            if (task.transcription_time) {
                analysis.transcription_times.push(parseFloat(task.transcription_time));
            }
            if (task.processing_time || task.time_used) {
                analysis.processing_times.push(parseFloat(task.processing_time || task.time_used));
            }
            
            // Video duration
            const duration = task.total_duration || task.video_duration || task.duration;
            if (duration) {
                analysis.total_durations.push(parseFloat(duration));
            }
            
            // Text analysis
            let fullText = task.full_text || task.corrected_text || task.original_text;
            if (!fullText && task.chunks) {
                const chunkTexts = task.chunks.filter(c => c.text).map(c => c.text);
                fullText = chunkTexts.join(' ').trim();
            }
            
            if (fullText) {
                const textLen = fullText.length;
                analysis.text_lengths.push(textLen);
                
                // Thai text detection
                const thaiChars = (fullText.match(/[\u0e00-\u0e7f]/g) || []).length;
                if (thaiChars > 0) {
                    analysis.thai_text_quality.has_thai++;
                    analysis.thai_text_quality.total_chars += textLen;
                    analysis.thai_text_quality.thai_chars += thaiChars;
                }
            }
            
            // Chunk count
            if (task.chunks && task.chunks.length > 0) {
                analysis.chunk_counts.push(task.chunks.length);
            }
        } else if (status === 'failed') {
            analysis.failed++;
            analysis.errors.push({
                task_id: (task.task_id || task.id || '').substring(0, 16) + '...',
                error: (task.error || task.error_message || 'Unknown error').substring(0, 200)
            });
        }
    });
    
    monitorAnalysis = { tasks, analysis, serverName };
    
    // Display analysis
    displayAnalysis(analysis);
    
    // Show results section
    document.getElementById('monitorResultsSection').style.display = 'block';
    document.getElementById('monitorResultsSection').scrollIntoView({ behavior: 'smooth' });
}

function displayAnalysis(analysis) {
    const analysisDiv = document.getElementById('monitorAnalysis');
    if (!analysisDiv) return;
    
    const successRate = analysis.total_tasks > 0 
        ? ((analysis.completed / analysis.total_tasks) * 100).toFixed(1) 
        : 0;
    
    let html = `
        <div class="analysis-summary">
            <div class="analysis-stat-card">
                <div class="analysis-stat-value">${analysis.total_tasks}</div>
                <div class="analysis-stat-label">Total Tasks</div>
            </div>
            <div class="analysis-stat-card" style="border-left: 4px solid var(--apple-green);">
                <div class="analysis-stat-value" style="color: var(--apple-green);">${analysis.completed}</div>
                <div class="analysis-stat-label">Completed</div>
            </div>
            <div class="analysis-stat-card" style="border-left: 4px solid #ff3b30;">
                <div class="analysis-stat-value" style="color: #ff3b30;">${analysis.failed}</div>
                <div class="analysis-stat-label">Failed</div>
            </div>
            <div class="analysis-stat-card" style="border-left: 4px solid var(--apple-blue);">
                <div class="analysis-stat-value" style="color: var(--apple-blue);">${successRate}%</div>
                <div class="analysis-stat-label">Success Rate</div>
            </div>
        </div>
    `;
    
    // Processing times
    if (analysis.processing_times.length > 0) {
        const times = analysis.processing_times;
        const avg = (times.reduce((a, b) => a + b, 0) / times.length).toFixed(2);
        const min = Math.min(...times).toFixed(2);
        const max = Math.max(...times).toFixed(2);
        
        html += `
            <div class="analysis-section">
                <h3>⏱️ Processing Times</h3>
                <div class="analysis-metrics">
                    <div class="metric-item">
                        <span class="metric-label">Average:</span>
                        <span class="metric-value">${avg}s</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">Min:</span>
                        <span class="metric-value">${min}s</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">Max:</span>
                        <span class="metric-value">${max}s</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Thai text quality
    if (analysis.thai_text_quality.has_thai > 0) {
        const thaiRatio = analysis.thai_text_quality.total_chars > 0
            ? ((analysis.thai_text_quality.thai_chars / analysis.thai_text_quality.total_chars) * 100).toFixed(1)
            : 0;
        
        html += `
            <div class="analysis-section">
                <h3>🇹🇭 Thai Text Quality</h3>
                <div class="analysis-metrics">
                    <div class="metric-item">
                        <span class="metric-label">Tasks with Thai:</span>
                        <span class="metric-value">${analysis.thai_text_quality.has_thai}/${analysis.completed}</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">Thai Character Ratio:</span>
                        <span class="metric-value">${thaiRatio}%</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">Total Thai Chars:</span>
                        <span class="metric-value">${analysis.thai_text_quality.thai_chars.toLocaleString()}</span>
                    </div>
                </div>
            </div>
        `;
    } else if (analysis.completed > 0) {
        html += `
            <div class="analysis-section">
                <h3>🇹🇭 Thai Text Quality</h3>
                <div class="analysis-warning">
                    ⚠️ No Thai text detected in completed tasks
                </div>
            </div>
        `;
    }
    
    // Errors
    if (analysis.errors.length > 0) {
        html += `
            <div class="analysis-section">
                <h3>❌ Errors (${analysis.errors.length})</h3>
                <div class="errors-list">
                    ${analysis.errors.slice(0, 10).map(error => `
                        <div class="error-item">
                            <strong>${error.task_id}:</strong> ${error.error}
                        </div>
                    `).join('')}
                    ${analysis.errors.length > 10 ? `<div class="error-item">... and ${analysis.errors.length - 10} more errors</div>` : ''}
                </div>
            </div>
        `;
    }
    
    analysisDiv.innerHTML = html;
}

function exportResults() {
    if (!monitorAnalysis) {
        alert('No results to export');
        return;
    }
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = `test_results_${monitorAnalysis.serverName}_${timestamp}.json`;
    
    const data = {
        server_name: monitorAnalysis.serverName,
        timestamp: timestamp,
        start_time: monitorStartTime ? monitorStartTime.toISOString() : null,
        end_time: new Date().toISOString(),
        task_ids: monitorTaskIds,
        task_data: monitorAnalysis.tasks,
        analysis: monitorAnalysis.analysis
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    alert(`✅ Results exported to ${filename}`);
}

async function loadPreviousResults() {
    const listDiv = document.getElementById('previousResultsList');
    if (!listDiv) return;
    
    try {
        // Try to get list of previous results from API
        // For now, show message
        listDiv.innerHTML = `
            <div style="padding: 24px; text-align: center; color: var(--apple-gray-3);">
                <p>Previous monitoring results are saved in:</p>
                <code style="background: var(--apple-gray-1); padding: 8px 16px; border-radius: 8px; display: inline-block; margin-top: 8px;">
                    dashboard/monitoring_results/
                </code>
                <p style="margin-top: 16px; font-size: 14px;">
                    💡 Use command line tool to view previous results:<br>
                    <code style="background: var(--apple-gray-1); padding: 4px 8px; border-radius: 4px; font-size: 12px;">
                        python monitor_test_jobs.py --server 4000-ada-sc --count 50
                    </code>
                </p>
            </div>
        `;
    } catch (error) {
        console.error('Error loading previous results:', error);
        listDiv.innerHTML = '<div class="error">Error loading previous results</div>';
    }
}

// Export functions
window.onMonitorServerChange = onMonitorServerChange;
window.onMonitorMethodChange = onMonitorMethodChange;
window.startMonitoring = startMonitoring;
window.stopMonitoring = stopMonitoring;
window.exportResults = exportResults;
window.loadPreviousResults = loadPreviousResults;
window.stopMonitorRefresh = stopMonitorRefresh;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Set up form listeners
    document.getElementById('monitorServer')?.addEventListener('change', onMonitorServerChange);
    document.getElementById('monitorMethod')?.addEventListener('change', onMonitorMethodChange);
    document.getElementById('monitorBatchId')?.addEventListener('input', updateMonitorStartButton);
    document.getElementById('monitorTaskIds')?.addEventListener('input', updateMonitorStartButton);
    document.getElementById('monitorCount')?.addEventListener('input', updateMonitorStartButton);
    
    // Initial setup
    onMonitorMethodChange();
});

