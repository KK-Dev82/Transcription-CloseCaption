/**
 * API Client for Transcription Service Dashboard
 * Separated fetch logic similar to React hooks pattern
 */

// Server configurations
// ⚠️ Update these values in server_constants.py on the server side
// This file is kept for backward compatibility and will be injected from backend
const SERVER_CONFIGS = {
    '4000-ada': { name: '4000-ada', api_url: 'http://87.197.119.40:40134' },
    '4000-ada-sc': { name: '4000-ada-sc', api_url: 'http://213.173.108.6:14237' },
    '5080': { name: '5080', api_url: 'http://213.144.200.206:15267' }
};

/**
 * Base API client with timeout and error handling
 */
class APIClient {
    constructor(baseURL = '', defaultTimeout = 5000) {
        this.baseURL = baseURL;
        this.defaultTimeout = defaultTimeout;
    }

    async get(endpoint, options = {}) {
        const { timeout = this.defaultTimeout, params = {} } = options;
        
        // Handle relative URLs (for local dashboard)
        let fullUrl;
        if (this.baseURL) {
            fullUrl = new URL(endpoint, this.baseURL);
        } else {
            // Relative URL - use endpoint directly
            fullUrl = endpoint.startsWith('/') ? endpoint : '/' + endpoint;
        }
        
        // Build URL with query params
        let urlString;
        if (typeof fullUrl === 'string') {
            // Relative URL
            urlString = fullUrl;
            const searchParams = new URLSearchParams();
            Object.keys(params).forEach(key => {
                if (params[key]) {
                    searchParams.append(key, params[key]);
                }
            });
            if (searchParams.toString()) {
                urlString += (urlString.includes('?') ? '&' : '?') + searchParams.toString();
            }
        } else {
            // Absolute URL
            Object.keys(params).forEach(key => {
                if (params[key]) {
                    fullUrl.searchParams.append(key, params[key]);
                }
            });
            urlString = fullUrl.toString();
        }

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), timeout * 1000);

            const response = await fetch(urlString, {
                ...options,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            return await response.json();
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error(`Request timeout after ${timeout}s`);
            }
            throw error;
        }
    }

    async post(endpoint, data, options = {}) {
        const { timeout = this.defaultTimeout } = options;
        
        // Handle empty baseURL (for relative URLs)
        let urlString;
        if (this.baseURL) {
            const url = new URL(endpoint, this.baseURL);
            urlString = url.toString();
        } else {
            // Relative URL - use endpoint directly
            urlString = endpoint.startsWith('/') ? endpoint : '/' + endpoint;
        }

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), timeout * 1000);

            const response = await fetch(urlString, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                body: JSON.stringify(data),
                signal: controller.signal,
                ...options
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            return await response.json();
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error(`Request timeout after ${timeout}s`);
            }
            throw error;
        }
    }

    async delete(endpoint, options = {}) {
        const { timeout = this.defaultTimeout } = options;
        
        // Handle relative URLs
        let urlString;
        if (this.baseURL) {
            const url = new URL(endpoint, this.baseURL);
            urlString = url.toString();
        } else {
            urlString = endpoint.startsWith('/') ? endpoint : '/' + endpoint;
        }

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), timeout * 1000);

            const response = await fetch(urlString, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                signal: controller.signal,
                ...options
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            return await response.json();
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error(`Request timeout after ${timeout}s`);
            }
            throw error;
        }
    }
}

/**
 * Dashboard API Client (for local dashboard endpoints)
 */
class DashboardAPI extends APIClient {
    constructor() {
        super('', 10); // localhost, 10s default timeout
    }

    async getServerSummary(serverName) {
        return this.get(`/api/server/${serverName}/summary`, { timeout: 5 });
    }

    async getServerStatus(serverName) {
        return this.get(`/api/server/${serverName}/status`, { timeout: 5 });
    }

    async getServerTasks(serverName, options = {}) {
        const { limit = 50, status = null, timeout = 60 } = options;  // เพิ่ม timeout เป็น 60s, ลด default limit
        const params = { limit };
        if (status) params.status = status;
        return this.get(`/api/server/${serverName}/tasks`, { params, timeout });
    }

    async getServerVideos(serverName) {
        return this.get(`/api/server/${serverName}/videos`, { timeout: 30 });  // เพิ่ม timeout เป็น 30s
    }

    async getServers() {
        return this.get('/api/servers', { timeout: 5 });
    }

    async startBatchTranscription(request) {
        return this.post('/api/batch/transcription', request, { timeout: 10 });
    }

    async getBatchStatus(batchId) {
        return this.get(`/api/batch/${batchId}`, { timeout: 5 });
    }

    async markTasksStopped(serverName, statuses = ['pending', 'processing']) {
        return this.post(`/api/server/${serverName}/tasks/mark-stopped`, { statuses }, { timeout: 30 });
    }

    async clearTasks(serverName, statuses = null) {
        return this.post(`/api/server/${serverName}/tasks/clear`, { statuses }, { timeout: 30 });
    }

    async getTaskStatus(serverName, taskId) {
        return this.get(`/api/server/${serverName}/task/${taskId}`, { timeout: 10 });
    }

    async checkTaskInQueue(serverName, taskId) {
        return this.get(`/api/server/${serverName}/queue/check-task/${taskId}`, { timeout: 30 });
    }

    async stopTask(serverName, taskId) {
        try {
            const response = await this.post(`/api/server/${serverName}/tasks/${taskId}/stop`, {}, { timeout: 30 });
            return response;
        } catch (error) {
            console.error(`Error stopping task ${taskId} on ${serverName}:`, error);
            return { success: false, error: error.message };
        }
    }
}

/**
 * Remote Server API Client (for direct remote server endpoints)
 */
class RemoteServerAPI extends APIClient {
    constructor(serverName) {
        const config = SERVER_CONFIGS[serverName];
        if (!config) {
            throw new Error(`Server ${serverName} not found`);
        }
        super(config.api_url, 30); // Remote server, 30s default timeout
        this.serverName = serverName;
    }

    async getTasks(options = {}) {
        const { limit = null, status = null } = options;
        const params = {};
        if (limit) params.limit = limit;
        if (status) params.status = status;
        return this.get('/transcribe/', { params, timeout: 30 });
    }

    async getTaskStatus(taskId) {
        return this.get(`/transcribe/${taskId}`, { timeout: 10 });
    }

    async deleteTask(taskId) {
        return this.delete(`/transcribe/${taskId}`, { timeout: 10 });
    }

    async getHealth() {
        return this.get('/health', { timeout: 5 });
    }

    async getQueueHealth() {
        return this.get('/queue/health', { timeout: 5 });
    }

    async getControlStatus() {
        return this.get('/api/control/status', { timeout: 5 });
    }

    async getControlVideos() {
        return this.get('/api/control/videos', { timeout: 10 });
    }
}

// Create singleton instances
const dashboardAPI = new DashboardAPI();

// Export
window.APIClient = APIClient;
window.DashboardAPI = DashboardAPI;
window.RemoteServerAPI = RemoteServerAPI;
window.dashboardAPI = dashboardAPI;
window.SERVER_CONFIGS = SERVER_CONFIGS;

