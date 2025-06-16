"use client";

import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/apiClient';
// Import specific message types and Balance from useWebSocket
import { useWebSocket, TradingBotWebSocketMessage, BalanceUpdateMessage, Balance, OrderUpdateMessage } from '@/hooks/useWebSocket';

interface AccountBalanceResponse {
  status?: string;
  balances: Balance[];
  message?: string;
}

export default function DashboardPage() {
  const { isAuthenticated, isLoading: authIsLoading, username } = useAuth();
  const router = useRouter();

  const [balances, setBalances] = useState<Balance[]>([]);
  const [isFetchingInitialBalances, setIsFetchingInitialBalances] = useState(true); // For initial fetch
  const [fetchError, setFetchError] = useState<string | null>(null);

  const fetchInitialBalances = useCallback(async () => {
    if (!isAuthenticated) return; // Should not happen due to redirect

    console.log("Dashboard: Attempting to fetch initial balances...");
    setIsFetchingInitialBalances(true); // Indicate loading for initial fetch
    setFetchError(null);
    try {
      const response = await apiClient<AccountBalanceResponse>('/account/balance');
      setBalances(response.balances || []);
      console.log("Dashboard: Initial balances fetched successfully.", response.balances);
    } catch (err: any) {
      console.error('Failed to fetch initial balances:', err);
      setFetchError(err.data?.detail || err.message || 'Failed to load account balances.');
      setBalances([]);
    } finally {
      setIsFetchingInitialBalances(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]); // Only depends on isAuthenticated to trigger once on auth

  useEffect(() => {
    if (isAuthenticated) {
      fetchInitialBalances();
    }
  }, [isAuthenticated, fetchInitialBalances]);

  const handleWebSocketMessage = useCallback((message: TradingBotWebSocketMessage) => {
    if (message.type === 'balance_update') {
      console.log('Dashboard: Received balance_update via WebSocket:', message.balances);
      setBalances(message.balances);
      setFetchError(null);
      setIsFetchingInitialBalances(false); // Data is now live, not "initial loading"
    } else if (message.type === 'order_update') {
      console.log('Dashboard: Received order_update via WebSocket:', message);
      // Potentially show a toast/notification for order updates
      // Or trigger a re-fetch of related data if necessary (e.g. recent trades list)
    }
  }, []);

  const { isConnected: wsIsConnected } = useWebSocket({
    shouldConnect: isAuthenticated, // Connect only if authenticated
    onMessage: handleWebSocketMessage,
    onOpen: () => {
      console.log("Dashboard: WebSocket connected. (Re)Fetching initial balances if needed.");
      // Optional: Re-fetch initial balances on WS (re)connect if you suspect data might be stale
      // This could be useful if the WS connection drops and reconnects later.
      // However, be mindful of causing too many fetches. User stream should provide updates.
      // fetchInitialBalances(); // Consider if this is needed or if relying on stream is enough
    },
    onClose: () => console.log("Dashboard: WebSocket disconnected."),
  });

  useEffect(() => {
    if (!authIsLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, authIsLoading, router]);

  if (authIsLoading || (!isAuthenticated && !authIsLoading)) {
    return <div className="flex items-center justify-center min-h-[calc(100vh-200px)]"><p className="text-lg text-gray-400">Loading dashboard...</p></div>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
            <h1 className="text-3xl font-bold text-white">Dashboard</h1>
            <p className="text-lg text-gray-400">Welcome back, <span className="font-semibold text-indigo-400">{username || 'User'}</span>!</p>
        </div>
        <span className={`text-xs px-3 py-1.5 rounded-full font-medium ${wsIsConnected ? 'bg-green-700 text-green-100' : 'bg-red-700 text-red-100'}`}>
          WebSocket: {wsIsConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      <div className="mb-8 p-6 bg-gray-800 rounded-xl shadow-2xl">
        <h2 className="text-2xl font-semibold mb-4 text-indigo-400">Account Balances</h2>
        {isFetchingInitialBalances && !balances.length ? (
          <p className="text-gray-400 animate-pulse">Loading initial balances...</p>
        ) : fetchError ? (
          <p className="text-red-400 bg-red-900/30 p-3 rounded-md">{fetchError}</p>
        ) : balances.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-700">
              <thead className="bg-gray-750">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-indigo-300 uppercase tracking-wider">Asset</th>
                  <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-indigo-300 uppercase tracking-wider">Available</th>
                  <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-indigo-300 uppercase tracking-wider">Locked</th>
                </tr>
              </thead>
              <tbody className="bg-gray-800 divide-y divide-gray-700">
                {balances.map((balance) => (
                  <tr key={balance.asset} className="hover:bg-gray-750 transition-colors duration-150">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-white">{balance.asset}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300 text-right">{parseFloat(balance.free).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 8 })}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300 text-right">{parseFloat(balance.locked).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 8 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-400">No balances to display or account is empty. Waiting for WebSocket updates if connected...</p>
        )}
      </div>
      {/* ... other dashboard sections ... */}
       <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-gray-800 p-6 rounded-xl shadow-2xl">
          <h2 className="text-xl font-semibold mb-3 text-indigo-400">Active Strategies</h2>
          <p className="text-gray-400">Real-time strategy updates coming soon...</p>
        </div>
        <div className="bg-gray-800 p-6 rounded-xl shadow-2xl">
          <h2 className="text-xl font-semibold mb-3 text-indigo-400">Recent Trades (Live)</h2>
          <p className="text-gray-400">Live trade feed coming soon...</p>
        </div>
      </div>
    </div>
  );
}
