"use client";

import React, { useState, useEffect, useCallback } from 'react'; // Added useCallback
import SymbolInfo from '@/components/trading/SymbolInfo';
import OrderForm from '@/components/trading/OrderForm';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';

// Debounce function
function debounce<F extends (...args: any[]) => any>(func: F, waitFor: number) {
  let timeout: ReturnType<typeof setTimeout> | null = null;
  return (...args: Parameters<F>): Promise<ReturnType<F>> =>
    new Promise(resolve => {
      if (timeout) {
        clearTimeout(timeout);
      }
      timeout = setTimeout(() => resolve(func(...args)), waitFor);
    });
}


export default function TradingPage() {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [inputSymbol, setInputSymbol] = useState('BTCUSDT');

  const { isAuthenticated, isLoading: authIsLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!authIsLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, authIsLoading, router]);

  // Debounced version of setSymbol to avoid too many API calls while typing
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const debouncedSetSymbol = useCallback(debounce((value: string) => {
    if (value.trim()) {
      setSymbol(value.trim().toUpperCase());
    } else {
      // If input is cleared, maybe reset symbol to a default or handle appropriately
      setSymbol(''); // Or some default valid symbol like 'BTCUSDT'
    }
  }, 750), []); // 750ms debounce

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newInputValue = e.target.value;
    setInputSymbol(newInputValue);
    debouncedSetSymbol(newInputValue);
  };

  // Function to force symbol update, e.g., on button click
  const forceSymbolUpdate = () => {
     if (inputSymbol.trim()) {
      setSymbol(inputSymbol.trim().toUpperCase());
    } else {
      setSymbol(''); // Or default
    }
  };


  if (authIsLoading || (!isAuthenticated && !authIsLoading)) {
    return <div className="flex items-center justify-center min-h-[calc(100vh-200px)]"><p className="text-lg text-gray-400">Loading trading interface...</p></div>;
  }

  return (
    <div className="space-y-10"> {/* Increased spacing */}
      <h1 className="text-3xl font-bold text-white mb-8 text-center">Manual Trading</h1>

      <div className="p-6 bg-gray-800 rounded-xl shadow-2xl">
        <h2 className="text-xl font-semibold text-indigo-300 mb-4">Select Trading Symbol</h2>
        <div className="flex items-center space-x-3"> {/* Ensure items are aligned */}
          <div className="flex-grow">
            <label htmlFor="symbolInput" className="sr-only">Trading Symbol</label> {/* sr-only if placeholder is enough */}
            <input
              type="text"
              id="symbolInput"
              value={inputSymbol}
              onChange={handleInputChange}
              // onKeyPress={(e) => { if (e.key === 'Enter') forceSymbolUpdate(); }} // Optional: Enter key to force update
              className="block w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-lg text-white placeholder-gray-400"
              placeholder="e.g., ETHUSDT, ADAUSDT"
            />
          </div>
          <button
            onClick={forceSymbolUpdate} // Use this for explicit update
            className="px-6 py-3 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:ring-indigo-500 transition duration-150 ease-in-out whitespace-nowrap"
          >
            Load Symbol
          </button>
        </div>
        <SymbolInfo symbol={symbol} /> {/* SymbolInfo will use the 'symbol' state */}
      </div>

      {/* Conditionally render OrderForm only if a symbol is active and valid (SymbolInfo could confirm validity) */}
      {symbol && symbol.trim() !== "" ? (
         <OrderForm symbol={symbol} />
      ) : (
        <div className="text-center p-6 bg-gray-800 rounded-xl shadow-2xl">
            <p className="text-gray-400">Please enter and load a valid trading symbol to place orders.</p>
        </div>
      )}
    </div>
  );
}
