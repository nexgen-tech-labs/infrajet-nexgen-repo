import { useEffect, useRef, useState } from 'react';
import { WebSocketEvent } from '@/types/chat';

interface UseWebSocketProps {
  url: string;
  onMessage: (event: WebSocketEvent) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

export const useWebSocket = ({ 
  url, 
  onMessage, 
  onConnect, 
  onDisconnect, 
  onError 
}: UseWebSocketProps) => {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    wsRef.current = new WebSocket(url);

    wsRef.current.onopen = () => {
      setIsConnected(true);
      onConnect?.();
    };

    wsRef.current.onclose = (event) => {
      setIsConnected(false);
      onDisconnect?.();
      
      // Don't auto-reconnect on 1006 (abnormal closure) as it usually means server is not available
      // Only auto-reconnect on normal closures
      if (event.code !== 1006 && event.code !== 1000) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      }
    };

    wsRef.current.onerror = (error) => {
      setIsConnected(false);
      // Only call onError once to avoid spam
      if (wsRef.current?.readyState === WebSocket.CONNECTING) {
        onError?.(error);
      }
    };

    wsRef.current.onmessage = (event) => {
      try {
        const data: WebSocketEvent = JSON.parse(event.data);
        onMessage(data);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };
  };

  const disconnect = () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setIsConnected(false);
  };

  const sendMessage = (message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  };

  useEffect(() => {
    connect();
    
    return () => {
      disconnect();
    };
  }, [url]);

  return {
    isConnected,
    connect,
    disconnect,
    sendMessage
  };
};