"use client";

import React, { useState, FormEvent, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/apiClient';
import { useWebSocket, TradingBotWebSocketMessage, OrderUpdateMessage } from '@/hooks/useWebSocket';
import { useAuth } from '@/contexts/AuthContext';

interface OrderDetailFromApi {
  orderId?: string;
  symbol?: string;
  price?: string;
  origQty?: string;
  executedQty?: string;
  status?: string;
  [key: string]: any;
}

interface StrategyResponse {
  status: string;
  message?: string;
  orders_placed?: OrderDetailFromApi[];
}

export default function TwapForm() {
  const { isAuthenticated } = useAuth();
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
  const [totalQuantity, setTotalQuantity] = useState('');
  const [slices, setSlices] = useState('');
  const [intervalSeconds, setIntervalSeconds] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [responseMessage, setResponseMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [initiatedOrders, setInitiatedOrders] = useState<OrderDetailFromApi[]>([]);
  const [liveOrderUpdates, setLiveOrderUpdates] = useState<{[orderId: string]: OrderUpdateMessage}>({});

  const handleWebSocketMessage = useCallback((message: TradingBotWebSocketMessage) => {
    if (message.type === 'order_update') {
      const isRelevantOrder = initiatedOrders.some(o => o.orderId === message.orderId);
      if (isRelevantOrder) {
        console.log(`TwapForm: Relevant order update for ${message.orderId}:`, message);
        setLiveOrderUpdates(prev => ({ ...prev, [message.orderId]: message }));
      }
    }
  }, [initiatedOrders]);

  useWebSocket({ // This hook instance is specific to TwapForm
    shouldConnect: isAuthenticated,
    onMessage: handleWebSocketMessage,
  });

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setResponseMessage(null);
    setErrorMessage(null);
    setInitiatedOrders([]); // Clear previous strategy's orders
    setLiveOrderUpdates({}); // Clear previous live updates

    const payload = {
      symbol: symbol.toUpperCase(), side,
      totalQuantity: parseFloat(totalQuantity), slices: parseInt(slices, 10),
      intervalSeconds: parseInt(intervalSeconds, 10),
    };
    if (!payload.symbol || isNaN(payload.totalQuantity) || payload.totalQuantity <= 0 ||
        isNaN(payload.slices) || payload.slices <= 0 ||
        isNaN(payload.intervalSeconds) || payload.intervalSeconds <= 0) {
      setErrorMessage('Invalid input. Please check all fields.'); setIsLoading(false); return;
    }

    try {
      const response = await apiClient<StrategyResponse>('/strategies/twap', { method: 'POST', body: payload });
      setResponseMessage(response.message || `TWAP strategy initiated: ${response.status}`);
      setInitiatedOrders(response.orders_placed || []);
    } catch (err: any) {
      setErrorMessage(err.data?.detail || err.message || 'Failed to initiate TWAP strategy.');
    } finally {
      setIsLoading(false);
    }
  };

  const commonInputClass = "mt-1 block w-full px-3 py-2.5 bg-gray-700 border border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-white placeholder-gray-500";
  const commonLabelClass = "block text-sm font-medium text-gray-300";
  const commonButtonClass = "w-full py-2.5 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:ring-indigo-500 disabled:opacity-60 transition duration-150 ease-in-out";
  const feedbackSuccessClass = "mt-4 text-sm text-green-300 text-center bg-green-800 bg-opacity-40 p-3 rounded-md";
  const feedbackErrorClass = "mt-4 text-sm text-red-300 text-center bg-red-800 bg-opacity-40 p-3 rounded-md";


  return (
    <form onSubmit={handleSubmit} className="p-6 bg-gray-800 rounded-xl shadow-2xl space-y-5 max-w-lg mx-auto">
      <h3 className="text-xl font-semibold text-indigo-400 mb-4 text-center">TWAP Strategy</h3>
      <div><label htmlFor="twap-symbol" className={commonLabelClass}>Symbol</label><input type="text" id="twap-symbol" value={symbol} onChange={(e) => setSymbol(e.target.value)} className={commonInputClass} placeholder="BTCUSDT" required /></div>
      <div><label htmlFor="twap-side" className={commonLabelClass}>Side</label><select id="twap-side" value={side} onChange={(e) => setSide(e.target.value as 'BUY' | 'SELL')} className={commonInputClass}><option value="BUY">Buy</option><option value="SELL">Sell</option></select></div>
      <div><label htmlFor="twap-totalQuantity" className={commonLabelClass}>Total Quantity</label><input type="number" id="twap-totalQuantity" value={totalQuantity} onChange={(e) => setTotalQuantity(e.target.value)} className={commonInputClass} placeholder="0.1" step="any" required /></div>
      <div><label htmlFor="twap-slices" className={commonLabelClass}>Slices</label><input type="number" id="twap-slices" value={slices} onChange={(e) => setSlices(e.target.value)} className={commonInputClass} placeholder="10" step="1" min="1" required /></div>
      <div><label htmlFor="twap-intervalSeconds" className={commonLabelClass}>Interval (s)</label><input type="number" id="twap-intervalSeconds" value={intervalSeconds} onChange={(e) => setIntervalSeconds(e.target.value)} className={commonInputClass} placeholder="60" step="1" min="1" required /></div>

      <button type="submit" disabled={isLoading} className={commonButtonClass}>
        {isLoading ? 'Initiating TWAP...' : 'Start TWAP Strategy'}
      </button>

      {responseMessage && <p className={feedbackSuccessClass}>{responseMessage}</p>}
      {errorMessage && <p className={feedbackErrorClass}>{errorMessage}</p>}

      {initiatedOrders.length > 0 && (
        <div className="mt-4 p-3 bg-gray-750 rounded-md max-h-48 overflow-y-auto"> {/* Increased max-h */}
          <h4 className="text-md font-semibold text-gray-200 mb-2 sticky top-0 bg-gray-750 py-1">Initiated Orders:</h4>
          <ul className="list-disc list-inside text-xs text-gray-300 space-y-1.5">
            {initiatedOrders.map(order => {
              const liveUpdate = order.orderId ? liveOrderUpdates[order.orderId] : undefined;
              return (
                <li key={order.orderId || Math.random().toString()}> {/* Fallback key */}
                  ID: <span className="font-mono">{order.orderId || 'N/A'}</span>, Qty: {order.origQty}, Initial Status: {order.status}
                  {liveUpdate && (
                    <span className="ml-2 px-1.5 py-0.5 text-xs bg-yellow-600 text-yellow-100 rounded-md">
                      Live: {liveUpdate.status} (Exec: {liveUpdate.executedQuantity}, Price: {liveUpdate.lastExecutedPrice || liveUpdate.price})
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </form>
  );
}
