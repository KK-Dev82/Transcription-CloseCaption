/**
 * Live Streaming Service for Dashboard
 * Monitor RTMP server recordings and process with Transcription Service
 */

class LiveStreamingService {
    constructor(config = {}) {
        this.rtmpServerUrl = config.rtmpServerUrl || 'http://143.198.77.135:8080';
        this.transcriptionApiUrl = config.transcriptionApiUrl || 'http://localhost:8010';
        this.dashboardApiUrl = config.dashboardApiUrl || window.location.origin;
        this.channel = config.channel || 'channel1';
        this.pollInterval = config.pollInterval || 5000; // 5 seconds
        this.monitoring = false;
        this.processedFiles = new Set();
        this.monitoringInterval = null;
    }

    /**
     * Start monitoring recordings
     */
    async startMonitoring() {
        if (this.monitoring) {
            console.warn('Monitoring already started');
            return;
        }

        this.monitoring = true;
        console.log('🎬 Starting live streaming monitoring...');

        // Start polling
        this.monitoringInterval = setInterval(async () => {
            await this.checkNewRecordings();
        }, this.pollInterval);

        // Initial check
        await this.checkNewRecordings();
    }

    /**
     * Stop monitoring
     */
    stopMonitoring() {
        if (!this.monitoring) {
            return;
        }

        this.monitoring = false;
        if (this.monitoringInterval) {
            clearInterval(this.monitoringInterval);
            this.monitoringInterval = null;
        }
        console.log('🛑 Stopped live streaming monitoring');
    }

    /**
     * Check for new recordings
     */
    async checkNewRecordings() {
        try {
            const response = await fetch(`${this.dashboardApiUrl}/api/live-streaming/recordings?channel=${this.channel}`);
            const data = await response.json();

            if (data.recordings && data.recordings.length > 0) {
                for (const recording of data.recordings) {
                    const filename = recording.filename || recording.name || recording;
                    if (!this.processedFiles.has(filename)) {
                        await this.processRecording(filename);
                        this.processedFiles.add(filename);
                    }
                }
            }
        } catch (error) {
            console.error('Error checking recordings:', error);
        }
    }

    /**
     * Process recording with Transcription Service
     */
    async processRecording(filename) {
        try {
            console.log(`📝 Processing recording: ${filename}`);

            const response = await fetch(
                `${this.dashboardApiUrl}/api/live-streaming/process-recording?filename=${encodeURIComponent(filename)}&channel=${this.channel}`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                }
            );

            if (response.ok) {
                const result = await response.json();
                console.log(`✅ Recording sent to Transcription Service: ${result.task_id}`);
                
                // Emit event for UI update
                this.onRecordingProcessed(result);
                
                return result;
            } else {
                const error = await response.text();
                console.error(`❌ Failed to process recording: ${error}`);
                throw new Error(error);
            }
        } catch (error) {
            console.error(`Error processing recording ${filename}:`, error);
            throw error;
        }
    }

    /**
     * Get streaming status
     */
    async getStreamingStatus() {
        try {
            const response = await fetch(`${this.dashboardApiUrl}/api/live-streaming/status`);
            return await response.json();
        } catch (error) {
            console.error('Error getting streaming status:', error);
            return { rtmp_server: 'offline', error: error.message };
        }
    }

    /**
     * Get HLS playlist URL
     */
    getHLSPlaylistUrl(channel = null) {
        const ch = channel || this.channel;
        return `http://143.198.77.135:80/hls/${ch}.m3u8`;
    }

    /**
     * Get RTMP push URL
     */
    getRTMPPushUrl(channel = null) {
        const ch = channel || this.channel;
        return `rtmp://143.198.77.135:1935/live/${ch}`;
    }

    /**
     * Event handler for processed recordings
     */
    onRecordingProcessed(result) {
        // Override this method or listen to events
        const event = new CustomEvent('recordingProcessed', {
            detail: result
        });
        window.dispatchEvent(event);
    }
}

// Export for use in other scripts
if (typeof window !== 'undefined') {
    window.LiveStreamingService = LiveStreamingService;
}

