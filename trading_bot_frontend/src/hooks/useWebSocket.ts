"use client";

import { useState, useEffect, useRef, useCallback } from 'react';

// Define message types based on backend structure
interface WebSocketMessageBase {
  type: string;
}

export interface OrderUpdateMessage extends WebSocketMessageBase {
  type: 'order_update';
  orderId: string;
  symbol: string;
  side: string;
  orderType: string;
  status: string;
  quantity: string;
  price: string;
  executedQuantity: string;
  lastExecutedPrice?: string;
  commission?: string;
  commissionAsset?: string;
  transactionTime: number;
  orderTime?: number; // Added from bot_logic _process_user_data_message
}

// Balance interface for reusability
export interface Balance {
  asset: string;
  free: string;
  locked: string;
}

export interface BalanceUpdateMessage extends WebSocketMessageBase {
  type: 'balance_update';
  balances: Balance[];
}

export interface PingMessage extends WebSocketMessageBase {
  type: 'ping'; // For custom ping if implemented, or other server status messages
}

export type TradingBotWebSocketMessage = OrderUpdateMessage | BalanceUpdateMessage | PingMessage | { type: 'error', data: any; message?: string };


const WEBSOCKET_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/updates';

interface UseWebSocketOptions {
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
  onError?: (event: Event) => void;
  onMessage?: (message: TradingBotWebSocketMessage) => void;
  shouldConnect?: boolean;
}

export function useWebSocket({
  onOpen,
  onClose,
  onError,
  onMessage,
  shouldConnect = true,
}: UseWebSocketOptions) {
  const ws = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<TradingBotWebSocketMessage | null>(null);

  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const maxRetries = 5; // Max number of retries
  const retryInterval = 5000; // Retry every 5 seconds
  const currentRetries = useRef(0);

  const connect = useCallback(() => {
    if (!shouldConnect || (ws.current && ws.current.readyState === WebSocket.OPEN)) {
      return;
    }
    if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current);

    console.log(`Attempting to connect to WebSocket: ${WEBSOCKET_URL}`);
    ws.current = new WebSocket(WEBSOCKET_URL);
    // currentRetries.current = 0; // Reset retries only on explicit call to connect, not on auto-retry

    ws.current.onopen = (event) => {
      console.log('WebSocket connected successfully');
      setIsConnected(true);
      currentRetries.current = 0; // Reset retries on successful connection
      if (onOpen) onOpen(event);
    };

    ws.current.onmessage = (event) => {
      try {
        const messageData = JSON.parse(event.data as string) as TradingBotWebSocketMessage;
        setLastMessage(messageData);
        if (onMessage) onMessage(messageData);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.current.onerror = (event) => {
      console.error('WebSocket error observed:', event);
      setIsConnected(false); // Ensure state reflects connection loss
      if (onError) onError(event);
      // Note: onclose will usually be called after onerror, which handles retry logic.
    };

    ws.current.onclose = (event) => {
      console.log(`WebSocket disconnected: Code=${event.code}, Reason='${event.reason}'`);
      setIsConnected(false);
      if (onClose) onClose(event);

      if (shouldConnect && event.code !== 1000 && currentRetries.current < maxRetries) {
        currentRetries.current++;
        console.log(`WebSocket: Retrying connection (attempt ${currentRetries.current}/${maxRetries}) in ${retryInterval / 1000}s...`);
        retryTimeoutRef.current = setTimeout(connect, retryInterval);
      } else if (currentRetries.current >= maxRetries) {
        console.error('WebSocket: Maximum retries reached. Giving up automatic reconnection.');
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldConnect, onOpen, onClose, onError, onMessage]); // Removed 'connect' from here as it causes infinite loops if not careful

  const disconnect = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    if (ws.current) {
      console.log('Manually disconnecting WebSocket.');
      ws.current.onclose = null; // Prevent onclose handler from trying to reconnect
      ws.current.close(1000, "Manual disconnection by client");
      ws.current = null;
      setIsConnected(false); // Explicitly set disconnected state
    }
  }, []);


  useEffect(() => {
    if (shouldConnect) {
      currentRetries.current = 0; // Reset retries when shouldConnect becomes true
      connect();
    } else {
      disconnect();
    }
    return () => {
      disconnect(); // Cleanup on component unmount
    };
  }, [shouldConnect, connect, disconnect]);

  const sendMessage = useCallback((message: string | object) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      const dataToSend = typeof message === 'object' ? JSON.stringify(message) : message;
      ws.current.send(dataToSend);
    } else {
      console.error('WebSocket is not connected. Cannot send message.');
    }
  }, []);

  return { isConnected, lastMessage, sendMessage, connectWebSocket: connect, disconnectWebSocket: disconnect };
}
