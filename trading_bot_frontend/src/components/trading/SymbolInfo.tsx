"use client";

import React, { useState, useEffect } from 'react';
import { apiClient } from '@/lib/apiClient';

interface SymbolFilter {
  filterType: string;
  [key: string]: any; // For other properties within filter
}

interface SymbolData {
  symbol: string;
  status: string;
  baseAsset: string;
  baseAssetPrecision: number;
  quoteAsset: string;
  quotePrecision: number;
  orderTypes: string[];
  icebergAllowed: boolean;
  ocoAllowed: boolean;
  isSpotTradingAllowed: boolean;
  isMarginTradingAllowed: boolean;
  filters: SymbolFilter[];
  permissions: string[];
  defaultSelfTradePreventionMode: string;
  allowedSelfTradePreventionModes: string[];
}

interface SymbolInfoResponse {
  status?: string; // Make optional as it's for our app structure not Binance's direct symbol info
  data: SymbolData;
}

interface SymbolInfoProps {
  symbol: string;
}

export default function SymbolInfo({ symbol }: SymbolInfoProps) {
  const [info, setInfo] = useState<SymbolData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (symbol && symbol.trim() !== "") { // Ensure symbol is not empty
      const fetchInfo = async () => {
        setIsLoading(true);
        setError(null);
        try {
          // apiClient response for /symbols/{symbol_name} is SymbolInfoResponse
          // which has { status: "success", data: SymbolData }
          const response = await apiClient<SymbolInfoResponse>(`/symbols/${symbol.toUpperCase()}`);
          if (response && response.data) { // Check if response and response.data are not null
            setInfo(response.data);
          } else {
            setInfo(null); // Set info to null if data is not what's expected
            setError(`No data returned for ${symbol.toUpperCase()}.`);
          }
        } catch (err: any) {
          console.error(`Failed to fetch info for ${symbol}:`, err);
          setError(err.data?.detail || err.message || `Failed to load info for ${symbol}.`);
          setInfo(null);
        } finally {
          setIsLoading(false);
        }
      };
      fetchInfo();
    } else {
      setInfo(null);
      setError(null); // Clear error if symbol is cleared
      setIsLoading(false); // Not loading if no symbol
    }
  }, [symbol]);

  if (!symbol || symbol.trim() === "") {
    return <p className="text-sm text-gray-400 mt-4">Enter a symbol (e.g., BTCUSDT, ETHUSDT) to see its trading information.</p>;
  }
  if (isLoading) {
    return <p className="text-sm text-indigo-300 animate-pulse mt-4">Loading symbol information for {symbol.toUpperCase()}...</p>;
  }
  if (error) {
    return <p className="text-sm text-red-400 mt-4">{error}</p>;
  }
  if (!info) {
    return <p className="text-sm text-gray-400 mt-4">No information available for {symbol.toUpperCase()}. It might be an invalid symbol.</p>;
  }

  const lotSizeFilter = info.filters.find(f => f.filterType === 'LOT_SIZE');
  const priceFilter = info.filters.find(f => f.filterType === 'PRICE_FILTER');
  // Binance uses 'NOTIONAL' for spot and 'MIN_NOTIONAL' for margin/futures, so check both.
  const minNotionalFilter = info.filters.find(f => f.filterType === 'NOTIONAL' || f.filterType === 'MIN_NOTIONAL');


  return (
    <div className="p-4 bg-gray-850 rounded-lg shadow-md mt-4 border border-gray-700"> {/* Slightly different bg */}
      <h3 className="text-lg font-semibold text-indigo-300 mb-3">Trading Information: <span className="text-white">{info.symbol}</span></h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-2 text-sm">
        <p><strong className="text-gray-400">Status:</strong> <span className="text-gray-200">{info.status}</span></p>
        <p><strong className="text-gray-400">Spot Trading:</strong> <span className={info.isSpotTradingAllowed ? "text-green-400" : "text-red-400"}>{info.isSpotTradingAllowed ? 'Allowed' : 'Not Allowed'}</span></p>
        <p><strong className="text-gray-400">Base Asset:</strong> <span className="text-gray-200">{info.baseAsset} (Prec: {info.baseAssetPrecision})</span></p>
        <p><strong className="text-gray-400">Quote Asset:</strong> <span className="text-gray-200">{info.quoteAsset} (Prec: {info.quotePrecision})</span></p>

        {lotSizeFilter && (
          <>
            <p><strong className="text-gray-400">Min Qty:</strong> <span className="text-gray-200">{lotSizeFilter.minQty}</span></p>
            <p><strong className="text-gray-400">Max Qty:</strong> <span className="text-gray-200">{lotSizeFilter.maxQty}</span></p>
            <p><strong className="text-gray-400">Step Size:</strong> <span className="text-gray-200">{lotSizeFilter.stepSize}</span></p>
          </>
        )}
        {priceFilter && (
          <>
            <p><strong className="text-gray-400">Min Price:</strong> <span className="text-gray-200">{priceFilter.minPrice}</span></p>
            <p><strong className="text-gray-400">Max Price:</strong> <span className="text-gray-200">{priceFilter.maxPrice}</span></p>
            <p><strong className="text-gray-400">Tick Size:</strong> <span className="text-gray-200">{priceFilter.tickSize}</span></p>
          </>
        )}
        {minNotionalFilter && ( // Check for specific notional key based on filter type
            <p><strong className="text-gray-400">Min Notional:</strong> <span className="text-gray-200">{minNotionalFilter.filterType === 'NOTIONAL' ? minNotionalFilter.notional : minNotionalFilter.minNotional}</span></p>
        )}
        <p className="md:col-span-full lg:col-span-3"><strong className="text-gray-400">Order Types:</strong> <span className="text-gray-200">{info.orderTypes.join(', ')}</span></p>
      </div>
    </div>
  );
}
