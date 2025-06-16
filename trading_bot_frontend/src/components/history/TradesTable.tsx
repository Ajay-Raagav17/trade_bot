"use client";

import React from 'react';
// Assuming Trade schema/interface is defined elsewhere and imported
// For example, from a shared types file or directly from backend schemas (if transformed for frontend)
import { Trade } from '@/schemas/trade_schemas'; // Adjust path if your schemas are elsewhere
import { format, parseISO } from 'date-fns'; // For date formatting

interface TradesTableProps {
  trades: Trade[]; // Expecting the Trade schema from trade_schemas.py (after JSON conversion)
  isLoading: boolean;
}

export default function TradesTable({ trades, isLoading }: TradesTableProps) {

  // Show loading state only if there are no trades from a previous page/fetch
  if (isLoading && trades.length === 0) {
    return (
      <div className="text-center py-10 bg-gray-800 shadow-xl rounded-lg">
        <div className="flex justify-center items-center">
          <div className="spinner mr-3"></div> {/* Using spinner class from globals.css */}
          <p className="text-indigo-300">Loading trades...</p>
        </div>
      </div>
    );
  }

  if (!isLoading && trades.length === 0) {
    return (
      <div className="text-center py-16 bg-gray-800 shadow-xl rounded-lg">
        <svg className="mx-auto h-12 w-12 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <h3 className="mt-2 text-lg font-medium text-gray-300">No Trades Found</h3>
        <p className="mt-1 text-sm text-gray-500">There are no trades matching your current filter criteria.</p>
      </div>
    );
  }

  const formatDecimal = (value: string | number | null | undefined, digits: number = 8) => {
    if (value === null || value === undefined) return '-';
    try {
      const num = parseFloat(value.toString());
      return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: digits });
    } catch {
      return '-';
    }
  };

  const calculateTotalValue = (trade: Trade): string => {
    if (trade.price_avg_filled && trade.quantity_filled) {
      try {
        const price = parseFloat(trade.price_avg_filled.toString());
        const quantity = parseFloat(trade.quantity_filled.toString());
        if (!isNaN(price) && !isNaN(quantity)) {
          return (price * quantity).toFixed(2); // Defaulting to 2 decimal places for value
        }
      } catch {
        return 'N/A';
      }
    }
    return 'N/A';
  };

  // Helper to determine quote asset from symbol string (basic implementation)
  const getQuoteAsset = (symbol: string): string => {
    if (symbol.endsWith('USDT')) return 'USDT';
    if (symbol.endsWith('BUSD')) return 'BUSD';
    if (symbol.endsWith('USDC')) return 'USDC';
    if (symbol.endsWith('BTC')) return 'BTC';
    if (symbol.endsWith('ETH')) return 'ETH';
    // Add more common quote assets or improve logic if needed
    return ''; // Fallback
  }


  return (
    <div className="bg-gray-800 shadow-xl rounded-t-lg overflow-hidden"> {/* Note: rounded-b-lg will be on pagination component */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-700">
          <thead className="bg-gray-750 sticky top-0 z-10"> {/* Sticky header */}
            <tr>
              <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-indigo-300 uppercase tracking-wider">Date/Time (UTC)</th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-indigo-300 uppercase tracking-wider">Symbol</th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-indigo-300 uppercase tracking-wider">Type</th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-indigo-300 uppercase tracking-wider">Side</th>
              <th scope="col" className="px-4 py-3 text-right text-xs font-medium text-indigo-300 uppercase tracking-wider">Avg. Price</th>
              <th scope="col" className="px-4 py-3 text-right text-xs font-medium text-indigo-300 uppercase tracking-wider">Filled Qty</th>
              <th scope="col" className="px-4 py-3 text-right text-xs font-medium text-indigo-300 uppercase tracking-wider">Total Value</th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-indigo-300 uppercase tracking-wider">Status</th>
              <th scope="col" className="px-4 py-3 text-right text-xs font-medium text-indigo-300 uppercase tracking-wider">Fee</th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-indigo-300 uppercase tracking-wider">Order ID</th>
            </tr>
          </thead>
          <tbody className="bg-gray-800 divide-y divide-gray-700">
            {trades.map((trade) => (
              <tr key={trade.id} className="hover:bg-gray-700/60 transition-colors duration-150">
                <td title={trade.transaction_time.toString()} className="px-4 py-3 whitespace-nowrap text-sm text-gray-300">{format(parseISO(trade.transaction_time.toString()), 'yyyy-MM-dd HH:mm:ss')}</td>
                <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-white">{trade.symbol}</td>
                <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-300">{trade.order_type}</td>
                <td className={`px-4 py-3 whitespace-nowrap text-sm font-semibold ${trade.side.toUpperCase() === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>{trade.side.toUpperCase()}</td>
                <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-300 font-mono">{formatDecimal(trade.price_avg_filled, 2)}</td>
                <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-300 font-mono">{formatDecimal(trade.quantity_filled, 8)}</td>
                <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-300 font-mono">{calculateTotalValue(trade)} <span className="text-xs text-gray-500">{getQuoteAsset(trade.symbol)}</span></td>
                <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-300">{trade.status}</td>
                <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-400 font-mono">
                  {trade.commission_amount ? `${formatDecimal(trade.commission_amount, 8)} ${trade.commission_asset}` : '-'}
                </td>
                <td title={trade.binance_order_id} className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 font-mono hover:text-gray-300 cursor-help">
                  ...{trade.binance_order_id.slice(-10)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```
