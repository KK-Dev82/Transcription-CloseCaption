/**
 * 🚀 Production-Ready Transcription Hook (2025)
 * 
 * Features:
 * - WebSocket with automatic fallback to Polling
 * - Error handling และ retry logic
 * - Real-time progress updates
 * - Connection health monitoring
 */

import { useState, useEffect, useRef, useCallback } from 'react';

// Types
interface TranscriptionTask {
  task_id: string;
  status: 'processing' | 'completed' | 'failed' | 'queued' | 'started';
  progress: number;
  stage: string;
  created_at: string;
  updated_at?: string;
  completed_at?: string;
  filename?: string;
  full_text?: string;
  error_message?: string;
  results_available: boolean;
}

interface WebSocketMessage {
  type: 'transcription.started' | 'transcription.progress' | 'transcription.completed' | 'transcription.failed' | 'ping' | 'subscription';
  task_id?: string;
  timestamp: string;
  progress?: number;
  stage?: string;
  status?: string;
  results_summary?: any;
  error?: string;
}

interface UseTranscriptionOptions {
  userId: string;
  apiBaseUrl?: string;
  enableWebSocket?: boolean;
  pollingInterval?: number; // milliseconds
  maxRetries?: number;
}

interface UseTranscriptionReturn {
  // State
  currentTask: TranscriptionTask | null;
  tasks: TranscriptionTask[];
  isConnected: boolean;
  connectionType: 'websocket' | 'polling' | 'disconnected';
  error: string | null;
  
  // Actions
  startTranscription: (filePath: string, options?: { language?: string; model_size?: string }) => Promise<string>;
  subscribeToTask: (taskId: string) => void;
  getTaskStatus: (taskId: string) => Promise<TranscriptionTask | null>;
  refreshTasks: () => Promise<void>;
  
  // Connection management
  reconnect: () => void;
  disconnect: () => void;
}

export const useTranscription = (options: UseTranscriptionOptions): UseTranscriptionReturn => {
  const {
    userId,
    apiBaseUrl = '',
    enableWebSocket = true,
    pollingInterval = 3000,
    maxRetries = 5
  } = options;

  // State
  const [currentTask, setCurrentTask] = useState<TranscriptionTask | null>(null);
  const [tasks, setTasks] = useState<TranscriptionTask[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionType, setConnectionType] = useState<'websocket' | 'polling' | 'disconnected'>('disconnected');
  const [error, setError] = useState<string | null>(null);

  // Refs
  const websocketRef = useRef<WebSocket | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const retryCountRef = useRef(0);
  const subscribedTasksRef = useRef<Set<string>>(new Set());

  // WebSocket connection
  const connectWebSocket = useCallback(() => {
    if (!enableWebSocket) return;

    try {
      const wsUrl = `${apiBaseUrl.replace('http', 'ws')}/ws/transcription/${userId}`;
      console.log('🔄 Connecting to WebSocket:', wsUrl);
      
      const ws = new WebSocket(wsUrl);
      websocketRef.current = ws;

      ws.onopen = () => {
        console.log('🟢 WebSocket connected');
        setIsConnected(true);
        setConnectionType('websocket');
        setError(null);
        retryCountRef.current = 0;

        // Re-subscribe to tasks
        subscribedTasksRef.current.forEach(taskId => {
          ws.send(JSON.stringify({ type: 'subscribe', task_id: taskId }));
        });
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          console.log('📨 WebSocket message:', data);

          // Handle ping
          if (data.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong', timestamp: data.timestamp }));
            return;
          }

          // Update task status
          if (data.task_id && data.type.startsWith('transcription.')) {
            const taskUpdate: Partial<TranscriptionTask> = {
              task_id: data.task_id,
              status: data.status as any,
              progress: data.progress || 0,
              stage: data.stage || '',
              updated_at: data.timestamp,
            };

            if (data.type === 'transcription.completed') {
              taskUpdate.completed_at = data.timestamp;
              taskUpdate.results_available = true;
              if (data.results_summary?.full_text) {
                taskUpdate.full_text = data.results_summary.full_text;
              }
            }

            if (data.type === 'transcription.failed') {
              taskUpdate.error_message = data.error;
            }

            // Update current task
            setCurrentTask(prev => 
              prev?.task_id === data.task_id ? { ...prev, ...taskUpdate } : prev
            );

            // Update tasks list
            setTasks(prev => {
              const index = prev.findIndex(t => t.task_id === data.task_id);
              if (index >= 0) {
                const updated = [...prev];
                updated[index] = { ...updated[index], ...taskUpdate };
                return updated;
              }
              return prev;
            });
          }

        } catch (error) {
          console.error('❌ Error parsing WebSocket message:', error);
        }
      };

      ws.onclose = (event) => {
        console.log(`🔴 WebSocket closed: ${event.code}`);
        setIsConnected(false);
        websocketRef.current = null;

        // Auto-reconnect with exponential backoff
        if (retryCountRef.current < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 10000);
          console.log(`🔄 Reconnecting in ${delay}ms (attempt ${retryCountRef.current + 1})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            retryCountRef.current++;
            connectWebSocket();
          }, delay);
        } else {
          console.log('❌ Max retries reached, falling back to polling');
          startPolling();
        }
      };

      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        setError('WebSocket connection failed');
      };

    } catch (error) {
      console.error('❌ Failed to create WebSocket:', error);
      startPolling();
    }
  }, [userId, apiBaseUrl, enableWebSocket, maxRetries]);

  // Polling fallback
  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current) return;

    console.log('🔄 Starting polling mode');
    setConnectionType('polling');
    setIsConnected(true);

    const poll = async () => {
      try {
        // Poll subscribed tasks
        for (const taskId of subscribedTasksRef.current) {
          const response = await fetch(`${apiBaseUrl}/polling/task/${taskId}`);
          if (response.ok) {
            const taskData = await response.json();
            
            // Update current task
            setCurrentTask(prev => 
              prev?.task_id === taskId ? { ...prev, ...taskData } : prev
            );

            // Update tasks list
            setTasks(prev => {
              const index = prev.findIndex(t => t.task_id === taskId);
              if (index >= 0) {
                const updated = [...prev];
                updated[index] = { ...updated[index], ...taskData };
                return updated;
              }
              return prev;
            });
          }
        }
        
        setError(null);
      } catch (error) {
        console.error('❌ Polling error:', error);
        setError('Polling failed');
      }
    };

    // Start polling
    poll();
    pollingIntervalRef.current = setInterval(poll, pollingInterval);
  }, [apiBaseUrl, pollingInterval]);

  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  }, []);

  // API functions
  const startTranscription = useCallback(async (
    filePath: string, 
    options: { language?: string; model_size?: string } = {}
  ): Promise<string> => {
    try {
      const response = await fetch(`${apiBaseUrl}/transcribe-enhanced/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_path: filePath,
          language: options.language || 'th',
          model_size: options.model_size || 'base'
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();
      const taskId = result.task_id;

      // Create initial task
      const newTask: TranscriptionTask = {
        task_id: taskId,
        status: 'started',
        progress: 0,
        stage: 'initializing',
        created_at: new Date().toISOString(),
        results_available: false
      };

      setCurrentTask(newTask);
      setTasks(prev => [newTask, ...prev]);

      // Subscribe to task
      subscribeToTask(taskId);

      return taskId;
    } catch (error) {
      setError(`Failed to start transcription: ${error}`);
      throw error;
    }
  }, [apiBaseUrl]);

  const subscribeToTask = useCallback((taskId: string) => {
    subscribedTasksRef.current.add(taskId);

    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({
        type: 'subscribe',
        task_id: taskId
      }));
    }
  }, []);

  const getTaskStatus = useCallback(async (taskId: string): Promise<TranscriptionTask | null> => {
    try {
      // Try enhanced status first
      let response = await fetch(`${apiBaseUrl}/transcribe-enhanced/status/${taskId}`);
      
      if (!response.ok) {
        // Fallback to polling API
        response = await fetch(`${apiBaseUrl}/polling/task/${taskId}`);
      }

      if (response.ok) {
        return await response.json();
      }
      
      return null;
    } catch (error) {
      console.error('❌ Error getting task status:', error);
      return null;
    }
  }, [apiBaseUrl]);

  const refreshTasks = useCallback(async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/polling/tasks/recent?limit=10`);
      if (response.ok) {
        const data = await response.json();
        setTasks(data.recent_tasks);
      }
    } catch (error) {
      console.error('❌ Error refreshing tasks:', error);
    }
  }, [apiBaseUrl]);

  const reconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    retryCountRef.current = 0;
    
    if (enableWebSocket) {
      if (websocketRef.current) {
        websocketRef.current.close();
      }
      connectWebSocket();
    } else {
      stopPolling();
      startPolling();
    }
  }, [enableWebSocket, connectWebSocket, startPolling, stopPolling]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    stopPolling();
    
    if (websocketRef.current) {
      websocketRef.current.close(1000, 'Manual disconnect');
      websocketRef.current = null;
    }
    
    setIsConnected(false);
    setConnectionType('disconnected');
  }, [stopPolling]);

  // Initialize connection
  useEffect(() => {
    if (enableWebSocket) {
      connectWebSocket();
    } else {
      startPolling();
    }

    return () => {
      disconnect();
    };
  }, [enableWebSocket, connectWebSocket, startPolling, disconnect]);

  return {
    currentTask,
    tasks,
    isConnected,
    connectionType,
    error,
    startTranscription,
    subscribeToTask,
    getTaskStatus,
    refreshTasks,
    reconnect,
    disconnect
  };
};
