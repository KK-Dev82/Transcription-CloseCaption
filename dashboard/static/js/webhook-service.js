/**
 * Webhook Service for Dashboard
 * จัดการ webhook subscriptions และรับ real-time updates
 */
class WebhookService {
    constructor() {
        this.dashboardBaseUrl = window.location.origin;
        this.webhookUrl = `${this.dashboardBaseUrl}/api/webhook/transcription`;
        this.events = new Map(); // Store events by task_id
        this.pollingIntervals = new Map(); // Fallback polling intervals
        this.useWebhook = true; // Enable webhook by default
        this.fallbackToPolling = true; // Fallback to polling if webhook fails
        this.pollingInterval = 10000; // 10 seconds fallback polling
        
        console.log(`WebhookService initialized: ${this.webhookUrl}`);
    }

    /**
     * Get webhook URL for a specific server
     */
    getWebhookUrl(serverName = null) {
        // Use dashboard's webhook endpoint
        return this.webhookUrl;
    }

    /**
     * Subscribe to webhook for a task
     * This will be called when creating a transcription task
     */
    async subscribeTask(taskId, serverName = null) {
        if (!this.useWebhook) {
            console.log(`Webhook disabled, skipping subscription for task ${taskId}`);
            return;
        }

        try {
            // Store task for webhook tracking
            if (!this.events.has(taskId)) {
                this.events.set(taskId, {
                    taskId,
                    serverName,
                    subscribed: true,
                    lastUpdate: null,
                    events: []
                });
            }

            console.log(`✅ Subscribed to webhook for task ${taskId}`);
        } catch (error) {
            console.error(`Error subscribing to webhook for task ${taskId}:`, error);
            
            // Fallback to polling if webhook subscription fails
            if (this.fallbackToPolling) {
                this.startFallbackPolling(taskId, serverName);
            }
        }
    }

    /**
     * Start fallback polling for a task
     */
    startFallbackPolling(taskId, serverName) {
        if (this.pollingIntervals.has(taskId)) {
            return; // Already polling
        }

        console.log(`⚠️ Starting fallback polling for task ${taskId}`);
        
        const interval = setInterval(async () => {
            try {
                const updatedTask = await dashboardAPI.getTaskStatus(serverName, taskId);
                this.handleWebhookEvent({
                    taskId,
                    status: updatedTask.status,
                    progress: updatedTask.progress,
                    payload: updatedTask
                });
            } catch (error) {
                console.error(`Error in fallback polling for task ${taskId}:`, error);
            }
        }, this.pollingInterval);

        this.pollingIntervals.set(taskId, interval);
    }

    /**
     * Stop fallback polling for a task
     */
    stopFallbackPolling(taskId) {
        const interval = this.pollingIntervals.get(taskId);
        if (interval) {
            clearInterval(interval);
            this.pollingIntervals.delete(taskId);
        }
    }

    /**
     * Handle webhook event (called from webhook endpoint or polling)
     */
    handleWebhookEvent(event) {
        const { taskId, status, progress, payload } = event;
        
        if (!this.events.has(taskId)) {
            this.events.set(taskId, {
                taskId,
                serverName: null,
                subscribed: true,
                lastUpdate: new Date(),
                events: []
            });
        }

        const taskData = this.events.get(taskId);
        taskData.lastUpdate = new Date();
        taskData.events.push({
            timestamp: new Date().toISOString(),
            status,
            progress,
            payload
        });

        // Keep only last 50 events
        if (taskData.events.length > 50) {
            taskData.events = taskData.events.slice(-50);
        }

        // Dispatch custom event for UI to update
        window.dispatchEvent(new CustomEvent('webhook:task-update', {
            detail: {
                taskId,
                status,
                progress,
                payload
            }
        }));

        // Stop polling if task is completed or failed
        if (status === 'completed' || status === 'failed') {
            this.stopFallbackPolling(taskId);
        }
    }

    /**
     * Get latest event for a task
     */
    getLatestEvent(taskId) {
        const taskData = this.events.get(taskId);
        if (!taskData || taskData.events.length === 0) {
            return null;
        }
        return taskData.events[taskData.events.length - 1];
    }

    /**
     * Get all events for a task
     */
    getTaskEvents(taskId) {
        const taskData = this.events.get(taskId);
        return taskData ? taskData.events : [];
    }

    /**
     * Check if task is subscribed
     */
    isSubscribed(taskId) {
        return this.events.has(taskId) && this.events.get(taskId).subscribed;
    }

    /**
     * Unsubscribe from webhook for a task
     */
    unsubscribeTask(taskId) {
        this.stopFallbackPolling(taskId);
        this.events.delete(taskId);
        console.log(`Unsubscribed from webhook for task ${taskId}`);
    }

    /**
     * Clear all subscriptions
     */
    clearAll() {
        // Stop all polling
        for (const [taskId, interval] of this.pollingIntervals.entries()) {
            clearInterval(interval);
        }
        this.pollingIntervals.clear();
        this.events.clear();
        console.log('Cleared all webhook subscriptions');
    }
}

// Global webhook service instance
window.webhookService = new WebhookService();

