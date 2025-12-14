/**
 * Task Checker - UI สำหรับตรวจสอบ task ที่ค้างใน queue
 */

async function checkTaskInQueue(serverName, taskId) {
    const modal = document.getElementById('taskCheckerModal');
    const content = document.getElementById('taskCheckerContent');
    
    if (!modal) {
        console.error('Task checker modal not found');
        return;
    }
    
    // Show modal with loading
    modal.style.display = 'flex';
    content.innerHTML = '<div class="loading">กำลังตรวจสอบ task...</div>';
    
    try {
        const result = await dashboardAPI.checkTaskInQueue(serverName, taskId);
        
        // Render result
        let html = `
            <div class="task-checker-result">
                <h3>🔍 Task: ${taskId.substring(0, 24)}...</h3>
                
                <div class="checker-section">
                    <h4>📦 Storage</h4>
                    ${result.storage.found ? `
                        <div class="checker-item">
                            <strong>Status:</strong> <span class="status-badge status-${result.storage.status}">${result.storage.status}</span>
                        </div>
                        <div class="checker-item">
                            <strong>Progress:</strong> ${result.storage.progress}%
                        </div>
                        <div class="checker-item">
                            <strong>Current Stage:</strong> ${result.storage.current_stage || 'N/A'}
                        </div>
                        <div class="checker-item">
                            <strong>Stage Description:</strong> ${result.storage.stage_description || 'N/A'}
                        </div>
                        ${result.storage.error_message ? `
                            <div class="checker-item error">
                                <strong>Error:</strong> ${result.storage.error_message}
                            </div>
                        ` : ''}
                    ` : `
                        <div class="checker-item warning">⚠️ Task ไม่พบใน storage</div>
                    `}
                </div>
                
                <div class="checker-section">
                    <h4>📋 Queue Status</h4>
                    <div class="checker-item">
                        <strong>audio_extraction_queue:</strong>
                        <ul>
                            <li>Messages Ready: ${result.queues.audio_extraction_queue.messages_ready}</li>
                            <li>Consumers: ${result.queues.audio_extraction_queue.consumers}</li>
                            <li>Unacked: ${result.queues.audio_extraction_queue.unacked}</li>
                        </ul>
                    </div>
                    <div class="checker-item">
                        <strong>transcription_queue:</strong>
                        <ul>
                            <li>Messages Ready: ${result.queues.transcription_queue.messages_ready}</li>
                            <li>Consumers: ${result.queues.transcription_queue.consumers}</li>
                            <li>Unacked: ${result.queues.transcription_queue.unacked}</li>
                        </ul>
                    </div>
                </div>
                
                <div class="checker-section">
                    <h4>⚙️ Worker Status</h4>
                    ${result.worker.running ? `
                        <div class="checker-item success">
                            ✅ Video Worker กำลังทำงาน (PIDs: ${result.worker.pids.join(', ')})
                        </div>
                    ` : `
                        <div class="checker-item error">
                            ❌ Video Worker ไม่ทำงาน
                        </div>
                    `}
                </div>
                
                ${result.file.exists ? `
                    <div class="checker-section">
                        <h4>📁 File</h4>
                        <div class="checker-item">
                            ✅ ไฟล์มีอยู่ (Size: ${result.file.size_mb} MB)
                        </div>
                        <div class="checker-item">
                            <strong>Path:</strong> ${result.file.path}
                        </div>
                    </div>
                ` : result.file.path ? `
                    <div class="checker-section">
                        <h4>📁 File</h4>
                        <div class="checker-item error">
                            ❌ ไฟล์ไม่พบ: ${result.file.path}
                        </div>
                    </div>
                ` : ''}
                
                ${result.recommendations && result.recommendations.length > 0 ? `
                    <div class="checker-section">
                        <h4>💡 คำแนะนำ</h4>
                        <ul class="recommendations">
                            ${result.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
        `;
        
        content.innerHTML = html;
        
    } catch (error) {
        content.innerHTML = `
            <div class="error">
                <h3>❌ Error</h3>
                <p>${error.message || 'Unknown error'}</p>
            </div>
        `;
    }
}

function closeTaskCheckerModal() {
    const modal = document.getElementById('taskCheckerModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Export functions
window.checkTaskInQueue = checkTaskInQueue;
window.closeTaskCheckerModal = closeTaskCheckerModal;

