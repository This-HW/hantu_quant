import { useState, useEffect, useRef, useCallback } from 'react';
import type { WebSocketMessage, ConnectionStatus, RealtimeData } from '../types';

interface UseWebSocketOptions {
  onMessage?: (data: RealtimeData) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
}

interface UseWebSocketReturn {
  connectionStatus: ConnectionStatus;
  lastMessage: RealtimeData | null;
  sendMessage: (message: any) => void;
  connect: () => void;
  disconnect: () => void;
}

const useWebSocket = (
  url: string, 
  options: UseWebSocketOptions = {}
): UseWebSocketReturn => {
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectAttempts = 5,
    reconnectInterval = 3000
  } = options;

  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    connected: false,
    reconnectAttempts: 0,
    latency: undefined
  });
  
  const [lastMessage, setLastMessage] = useState<RealtimeData | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const lastPingRef = useRef<number>(0);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      wsRef.current = new WebSocket(url);
      
      wsRef.current.onopen = () => {
        setConnectionStatus(prev => ({
          ...prev,
          connected: true,
          lastConnected: new Date().toISOString(),
          reconnectAttempts: 0
        }));
        
        onConnect?.();
        
        // 핑/퐁으로 연결 상태 모니터링
        pingIntervalRef.current = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            lastPingRef.current = Date.now();
            wsRef.current.send(JSON.stringify({ type: 'ping', timestamp: lastPingRef.current }));
          }
        }, 30000); // 30초마다 핑
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          
          // 퐁 응답 처리
          if (message.type === 'pong') {
            const latency = Date.now() - lastPingRef.current;
            setConnectionStatus(prev => ({ ...prev, latency }));
            return;
          }
          
          // 일반 메시지 처리
          const realtimeData: RealtimeData = {
            type: message.type as RealtimeData['type'],
            timestamp: message.timestamp || new Date().toISOString(),
            data: message.data
          };
          
          setLastMessage(realtimeData);
          onMessage?.(realtimeData);
        } catch (error) {
          console.error('WebSocket 메시지 파싱 오류:', error);
        }
      };

      wsRef.current.onclose = () => {
        setConnectionStatus(prev => ({
          ...prev,
          connected: false
        }));
        
        onDisconnect?.();
        
        // 핑 인터벌 정리
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }
        
        // 자동 재연결 시도
        if (connectionStatus.reconnectAttempts < reconnectAttempts) {
          setConnectionStatus(prev => ({
            ...prev,
            reconnectAttempts: prev.reconnectAttempts + 1
          }));
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket 오류:', error);
        onError?.(error);
      };
      
    } catch (error) {
      console.error('WebSocket 연결 실패:', error);
    }
  }, [url, onConnect, onDisconnect, onError, onMessage, connectionStatus.reconnectAttempts, reconnectAttempts, reconnectInterval]);

  const disconnect = useCallback(() => {
    // 재연결 타임아웃 정리
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    // 핑 인터벌 정리
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    
    // WebSocket 연결 종료
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setConnectionStatus(prev => ({
      ...prev,
      connected: false,
      reconnectAttempts: 0
    }));
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const formattedMessage: WebSocketMessage = {
        type: message.type || 'message',
        data: message.data || message,
        timestamp: new Date().toISOString(),
        id: message.id || `msg_${Date.now()}`
      };
      
      wsRef.current.send(JSON.stringify(formattedMessage));
    } else {
      console.warn('WebSocket이 연결되지 않았습니다');
    }
  }, []);

  // 컴포넌트 마운트 시 자동 연결
  useEffect(() => {
    connect();
    
    // 컴포넌트 언마운트 시 정리
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  // 페이지 가시성 변경 시 연결 관리
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // 페이지가 숨겨졌을 때는 연결 유지하되 불필요한 데이터 전송 중지
        sendMessage({ type: 'pause_updates' });
      } else {
        // 페이지가 다시 보일 때 업데이트 재개
        if (connectionStatus.connected) {
          sendMessage({ type: 'resume_updates' });
        } else {
          connect();
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [connectionStatus.connected, connect, sendMessage]);

  return {
    connectionStatus,
    lastMessage,
    sendMessage,
    connect,
    disconnect
  };
};

export default useWebSocket; 