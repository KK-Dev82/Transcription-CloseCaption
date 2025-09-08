# 🚨 Error Handling Guide

## 🎯 **Overview**

การจัดการ errors แบบครอบคลุมสำหรับ Frontend integration กับ Transcription API

## 📋 **Error Categories**

### **1. Network Errors**
```typescript
interface NetworkError {
  type: 'NETWORK_ERROR';
  message: string;
  status?: number;
  retryable: boolean;
}

const handleNetworkError = (error: any): NetworkError => {
  if (error.name === 'TypeError' && error.message.includes('fetch')) {
    return {
      type: 'NETWORK_ERROR',
      message: 'ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้',
      retryable: true
    };
  }
  
  if (error.status >= 500) {
    return {
      type: 'NETWORK_ERROR',
      message: 'เซิร์ฟเวอร์มีปัญหา กรุณาลองใหม่อีกครั้ง',
      status: error.status,
      retryable: true
    };
  }
  
  return {
    type: 'NETWORK_ERROR',
    message: error.message || 'เกิดข้อผิดพลาดในการเชื่อมต่อ',
    status: error.status,
    retryable: false
  };
};
```

### **2. API Errors**
```typescript
interface APIError {
  type: 'API_ERROR';
  status: number;
  message: string;
  detail?: string;
  field?: string;
}

const handleAPIError = async (response: Response): Promise<APIError> => {
  let errorData: any = {};
  
  try {
    errorData = await response.json();
  } catch {
    // ถ้า parse JSON ไม่ได้
  }
  
  const errorMap: Record<number, string> = {
    400: 'ข้อมูลที่ส่งมาไม่ถูกต้อง',
    401: 'ไม่มีสิทธิ์เข้าใช้งาน',
    403: 'ไม่อนุญาตให้เข้าใช้งาน',
    404: 'ไม่พบข้อมูลที่ร้องขอ',
    409: 'ข้อมูลขัดแย้งกับข้อมูลที่มีอยู่',
    413: 'ไฟล์มีขนาดใหญ่เกินไป',
    422: 'ข้อมูลไม่ถูกต้องตามรูปแบบที่กำหนด',
    429: 'ส่งคำขอมากเกินไป กรุณารอสักครู่',
    500: 'เซิร์ฟเวอร์มีปัญหา',
    503: 'เซิร์ฟเวอร์ไม่สามารถให้บริการได้ชั่วคราว'
  };
  
  return {
    type: 'API_ERROR',
    status: response.status,
    message: errorMap[response.status] || 'เกิดข้อผิดพลาดที่ไม่ทราบสาเหตุ',
    detail: errorData.detail || errorData.message,
    field: errorData.field
  };
};
```

### **3. WebSocket Errors**
```typescript
interface WebSocketError {
  type: 'WEBSOCKET_ERROR';
  code: number;
  reason: string;
  reconnectable: boolean;
}

const handleWebSocketError = (event: CloseEvent): WebSocketError => {
  const errorMap: Record<number, { message: string; reconnectable: boolean }> = {
    1000: { message: 'การเชื่อมต่อปิดตามปกติ', reconnectable: false },
    1001: { message: 'เซิร์ฟเวอร์หยุดทำงาน', reconnectable: true },
    1005: { message: 'ไม่มีสถานะการปิด', reconnectable: true },
    1006: { message: 'การเชื่อมต่อหลุดอย่างผิดปกติ', reconnectable: true },
    1008: { message: 'การเชื่อมต่อถูกปฏิเสธ', reconnectable: false },
    1011: { message: 'เซิร์ฟเวอร์มีข้อผิดพลาด', reconnectable: true },
  };
  
  const errorInfo = errorMap[event.code] || { 
    message: 'ข้อผิดพลาดที่ไม่ทราบสาเหตุ', 
    reconnectable: true 
  };
  
  return {
    type: 'WEBSOCKET_ERROR',
    code: event.code,
    reason: errorInfo.message,
    reconnectable: errorInfo.reconnectable
  };
};
```

### **4. File Upload Errors**
```typescript
interface FileUploadError {
  type: 'FILE_UPLOAD_ERROR';
  reason: 'SIZE' | 'FORMAT' | 'NETWORK' | 'SERVER';
  message: string;
  maxSize?: number;
  allowedFormats?: string[];
}

const validateFile = (file: File): FileUploadError | null => {
  const maxSize = 500 * 1024 * 1024; // 500MB
  const allowedFormats = ['.mp4', '.mp3', '.wav', '.m4a', '.avi', '.mov'];
  
  if (file.size > maxSize) {
    return {
      type: 'FILE_UPLOAD_ERROR',
      reason: 'SIZE',
      message: `ไฟล์มีขนาดใหญ่เกินไป (${(file.size / 1024 / 1024).toFixed(2)}MB)`,
      maxSize: maxSize / 1024 / 1024
    };
  }
  
  const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
  if (!allowedFormats.includes(fileExtension)) {
    return {
      type: 'FILE_UPLOAD_ERROR',
      reason: 'FORMAT',
      message: `รูปแบบไฟล์ไม่รองรับ (${fileExtension})`,
      allowedFormats
    };
  }
  
  return null;
};
```

## 🔧 **Error Handler Hook**

```typescript
export const useErrorHandler = () => {
  const [errors, setErrors] = useState<Array<{
    id: string;
    error: any;
    timestamp: Date;
    dismissed: boolean;
  }>>([]);
  
  const addError = useCallback((error: any) => {
    const errorId = Date.now().toString();
    setErrors(prev => [...prev, {
      id: errorId,
      error,
      timestamp: new Date(),
      dismissed: false
    }]);
    
    // Auto-dismiss after 10 seconds for non-critical errors
    if (error.type !== 'API_ERROR' || error.status < 500) {
      setTimeout(() => {
        dismissError(errorId);
      }, 10000);
    }
  }, []);
  
  const dismissError = useCallback((errorId: string) => {
    setErrors(prev => prev.map(e => 
      e.id === errorId ? { ...e, dismissed: true } : e
    ));
  }, []);
  
  const clearErrors = useCallback(() => {
    setErrors([]);
  }, []);
  
  const handleError = useCallback(async (error: any, context?: string) => {
    console.error(`❌ Error in ${context}:`, error);
    
    let processedError: any;
    
    if (error instanceof Response) {
      processedError = await handleAPIError(error);
    } else if (error.type === 'close') {
      processedError = handleWebSocketError(error);
    } else if (error.name === 'TypeError' || error.message?.includes('fetch')) {
      processedError = handleNetworkError(error);
    } else {
      processedError = {
        type: 'UNKNOWN_ERROR',
        message: error.message || 'เกิดข้อผิดพลาดที่ไม่ทราบสาเหตุ'
      };
    }
    
    addError(processedError);
    return processedError;
  }, [addError]);
  
  return {
    errors: errors.filter(e => !e.dismissed),
    addError,
    dismissError,
    clearErrors,
    handleError
  };
};
```

## 🎨 **Error Display Components**

### **Error Toast Component**
```tsx
interface ErrorToastProps {
  error: any;
  onDismiss: () => void;
}

const ErrorToast: React.FC<ErrorToastProps> = ({ error, onDismiss }) => {
  const getErrorIcon = () => {
    switch (error.type) {
      case 'NETWORK_ERROR': return '🌐';
      case 'API_ERROR': return '⚠️';
      case 'WEBSOCKET_ERROR': return '🔌';
      case 'FILE_UPLOAD_ERROR': return '📁';
      default: return '❌';
    }
  };
  
  const getErrorColor = () => {
    if (error.type === 'API_ERROR' && error.status >= 500) return 'bg-red-500';
    if (error.type === 'NETWORK_ERROR' && !error.retryable) return 'bg-red-500';
    return 'bg-yellow-500';
  };
  
  return (
    <div className={`${getErrorColor()} text-white p-4 rounded-lg mb-2 flex items-center justify-between`}>
      <div className="flex items-center">
        <span className="text-xl mr-2">{getErrorIcon()}</span>
        <div>
          <p className="font-medium">{error.message}</p>
          {error.detail && (
            <p className="text-sm opacity-90">{error.detail}</p>
          )}
        </div>
      </div>
      <button 
        onClick={onDismiss}
        className="text-white hover:text-gray-200"
      >
        ✕
      </button>
    </div>
  );
};
```

### **Error Boundary**
```tsx
interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

class TranscriptionErrorBoundary extends React.Component<
  React.PropsWithChildren<{}>, 
  ErrorBoundaryState
> {
  constructor(props: React.PropsWithChildren<{}>) {
    super(props);
    this.state = { hasError: false };
  }
  
  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }
  
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('❌ React Error Boundary caught an error:', error, errorInfo);
    
    // Send error to monitoring service
    // sendErrorToMonitoring(error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100">
          <div className="bg-white p-8 rounded-lg shadow-lg max-w-md w-full">
            <div className="text-center">
              <div className="text-6xl mb-4">😵</div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                เกิดข้อผิดพลาด
              </h1>
              <p className="text-gray-600 mb-6">
                แอปพลิเคชันมีปัญหา กรุณาลองรีเฟรชหน้าเว็บ
              </p>
              <div className="space-y-3">
                <button 
                  onClick={() => window.location.reload()}
                  className="w-full bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600"
                >
                  🔄 รีเฟรชหน้าเว็บ
                </button>
                <button 
                  onClick={() => this.setState({ hasError: false })}
                  className="w-full bg-gray-500 text-white py-2 px-4 rounded hover:bg-gray-600"
                >
                  ↩️ ลองใหม่
                </button>
              </div>
              
              {process.env.NODE_ENV === 'development' && this.state.error && (
                <details className="mt-4 text-left">
                  <summary className="cursor-pointer text-sm text-gray-500">
                    รายละเอียดข้อผิดพลาด (Development)
                  </summary>
                  <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto">
                    {this.state.error.stack}
                  </pre>
                </details>
              )}
            </div>
          </div>
        </div>
      );
    }
    
    return this.props.children;
  }
}
```

## 🔄 **Retry Mechanisms**

### **Exponential Backoff Retry**
```typescript
const useRetryWithBackoff = () => {
  const retry = async <T>(
    fn: () => Promise<T>,
    maxAttempts: number = 3,
    baseDelay: number = 1000
  ): Promise<T> => {
    let lastError: any;
    
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;
        
        if (attempt === maxAttempts) {
          throw error;
        }
        
        // Exponential backoff with jitter
        const delay = baseDelay * Math.pow(2, attempt - 1) + Math.random() * 1000;
        console.log(`🔄 Retry attempt ${attempt}/${maxAttempts} in ${delay}ms`);
        
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    
    throw lastError;
  };
  
  return { retry };
};
```

### **Smart Retry for Different Error Types**
```typescript
const useSmartRetry = () => {
  const shouldRetry = (error: any): boolean => {
    // Network errors - always retry
    if (error.type === 'NETWORK_ERROR') return true;
    
    // API errors - retry only for server errors
    if (error.type === 'API_ERROR') {
      return error.status >= 500 || error.status === 429;
    }
    
    // WebSocket errors - retry if reconnectable
    if (error.type === 'WEBSOCKET_ERROR') {
      return error.reconnectable;
    }
    
    return false;
  };
  
  const getRetryDelay = (error: any, attempt: number): number => {
    if (error.status === 429) {
      // Rate limiting - longer delay
      return 5000 * attempt;
    }
    
    if (error.type === 'NETWORK_ERROR') {
      // Network issues - exponential backoff
      return 1000 * Math.pow(2, attempt - 1);
    }
    
    // Default delay
    return 2000 * attempt;
  };
  
  return { shouldRetry, getRetryDelay };
};
```

## 📊 **Error Monitoring**

### **Error Logging**
```typescript
const useErrorLogging = () => {
  const logError = (error: any, context: string, userId?: string) => {
    const errorLog = {
      timestamp: new Date().toISOString(),
      error: {
        type: error.type,
        message: error.message,
        stack: error.stack,
        status: error.status
      },
      context,
      userId,
      userAgent: navigator.userAgent,
      url: window.location.href
    };
    
    // Send to monitoring service
    console.error('📊 Error logged:', errorLog);
    
    // In production, send to your monitoring service
    // sendToMonitoringService(errorLog);
  };
  
  return { logError };
};
```

### **Error Recovery Strategies**
```typescript
const useErrorRecovery = () => {
  const recoverFromError = async (error: any, context: string) => {
    switch (error.type) {
      case 'WEBSOCKET_ERROR':
        // Try to reconnect WebSocket
        console.log('🔄 Attempting WebSocket recovery');
        // Implement reconnection logic
        break;
        
      case 'API_ERROR':
        if (error.status === 401) {
          // Redirect to login
          console.log('🔐 Redirecting to login');
          // window.location.href = '/login';
        }
        break;
        
      case 'NETWORK_ERROR':
        // Check network connectivity
        if (!navigator.onLine) {
          console.log('📡 Waiting for network connectivity');
          await waitForOnline();
        }
        break;
    }
  };
  
  const waitForOnline = (): Promise<void> => {
    return new Promise(resolve => {
      const handleOnline = () => {
        window.removeEventListener('online', handleOnline);
        resolve();
      };
      window.addEventListener('online', handleOnline);
    });
  };
  
  return { recoverFromError };
};
```

## 🧪 **Testing Error Scenarios**

```typescript
// Test error handling
describe('Error Handling', () => {
  test('should handle network errors gracefully', async () => {
    // Mock network failure
    global.fetch = jest.fn().mockRejectedValue(new TypeError('Network error'));
    
    const { result } = renderHook(() => useErrorHandler());
    
    // Trigger error
    await act(async () => {
      await result.current.handleError(new TypeError('Network error'), 'test');
    });
    
    expect(result.current.errors).toHaveLength(1);
    expect(result.current.errors[0].error.type).toBe('NETWORK_ERROR');
  });
  
  test('should retry failed requests', async () => {
    const mockFn = jest.fn()
      .mockRejectedValueOnce(new Error('Temporary error'))
      .mockResolvedValue('success');
    
    const { retry } = useRetryWithBackoff();
    const result = await retry(mockFn, 3);
    
    expect(mockFn).toHaveBeenCalledTimes(2);
    expect(result).toBe('success');
  });
});
```
