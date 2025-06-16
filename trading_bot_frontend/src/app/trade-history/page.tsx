"use client";

import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { apiClient } from '@/lib/apiClient';
import { Trade, PaginatedTradeHistoryResponse } from '@/schemas/trade_schemas'; // Assuming this path is correct
import TradesTable from '@/components/history/TradesTable';
import PaginationControls from '@/components/common/PaginationControls';
import TradeFilters, { TradeFilterValues } from '@/components/history/TradeFilters'; // Import new component and type
import { formatISO, parseISO, isValid as isValidDate } from 'date-fns'; // For date query param handling

const ITEMS_PER_PAGE = 15;

// Helper to create a query string from filter values, excluding empty/null/undefined
constcreateQueryString = (filters: TradeFilterValues, page: number, size: number): string => {
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('size', size.toString());

    Object.entries(filters).forEach(([key, value]) => {
        if (value !== '' && value !== undefined && value !== null) {
            params.append(key, value.toString());
        }
    });
    return params.toString();
};


export default function TradeHistoryPage() {
  const { isAuthenticated, isLoading: authIsLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [trades, setTrades] = useState<Trade[]>([]);
  const [totalTrades, setTotalTrades] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeFilters, setActiveFilters] = useState<TradeFilterValues>({});

  // Initialize filters and page from URL search params on component mount
  useEffect(() => {
    const pageFromUrl = parseInt(searchParams.get('page') || '1', 10);
    const initialFiltersFromUrl: TradeFilterValues = {
      symbol: searchParams.get('symbol') || undefined,
      order_id_search: searchParams.get('order_id_search') || undefined,
      start_time: searchParams.get('start_time') || undefined,
      end_time: searchParams.get('end_time') || undefined,
      side: (searchParams.get('side') as TradeFilterValues['side']) || undefined,
      order_type: searchParams.get('order_type') || undefined,
      status: searchParams.get('status') || undefined,
    };

    // Validate and format date strings from URL if they exist
    if (initialFiltersFromUrl.start_time) {
        const parsedStartDate = parseISO(initialFiltersFromUrl.start_time);
        if (!isValidDate(parsedStartDate)) initialFiltersFromUrl.start_time = undefined;
    }
    if (initialFiltersFromUrl.end_time) {
        const parsedEndDate = parseISO(initialFiltersFromUrl.end_time);
        if (!isValidDate(parsedEndDate)) initialFiltersFromUrl.end_time = undefined;
    }

    setActiveFilters(initialFiltersFromUrl);
    setCurrentPage(pageFromUrl);
  // Only run this on initial mount or if searchParams string itself changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.toString()]);


  const fetchTrades = useCallback(async (page: number, filters: TradeFilterValues) => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    setError(null);

    const queryString = createQueryString(filters, page, ITEMS_PER_PAGE);

    try {
      const data = await apiClient<PaginatedTradeHistoryResponse>(`/trades?${queryString}`);
      setTrades(data.trades || []);
      setTotalTrades(data.total);
      setCurrentPage(data.page);
      setTotalPages(data.pages !== null && data.pages !== undefined ? data.pages : Math.ceil(data.total / ITEMS_PER_PAGE));
    } catch (err: any) {
      console.error("Failed to fetch trade history:", err);
      setError(err.data?.detail || err.message || "Could not load trade history at this time.");
      setTrades([]);
      setTotalTrades(0);
      setTotalPages(0);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (!authIsLoading && !isAuthenticated) {
      router.replace('/login');
    } else if (isAuthenticated) {
      // Fetch trades whenever currentPage or activeFilters change and user is authenticated
      fetchTrades(currentPage, activeFilters);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, authIsLoading, currentPage, activeFilters, router]); // Removed fetchTrades from here to avoid potential loops if it's not stable

  const handleApplyFilters = useCallback((newFilters: TradeFilterValues) => {
    const params = new URLSearchParams();
    params.set('page', '1'); // Reset to page 1 when filters change

    Object.entries(newFilters).forEach(([key, value]) => {
      if (value) { // Ensure value is not null, undefined, or empty string
        params.append(key, value.toString());
      }
    });
    router.push(`${pathname}?${params.toString()}`);
    // useEffect listening to searchParams will update activeFilters and currentPage, then trigger fetch.
  }, [pathname, router]);

  const handlePageChange = (newPage: number) => {
    if (newPage !== currentPage) {
      const params = new URLSearchParams(searchParams.toString()); // Preserve existing filters
      params.set('page', newPage.toString());
      router.push(`${pathname}?${params.toString()}`);
      // useEffect listening to searchParams will update currentPage.
    }
  };

  if (authIsLoading || (!isAuthenticated && !authIsLoading && !error)) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-200px)]">
        <div className="spinner mr-3"></div>
        <p className="text-lg text-gray-400">Loading Trade History...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-2 sm:px-4 lg:px-6 py-8">
      <div className="flex flex-col sm:flex-row justify-between items-center gap-4 mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-white">Trade History</h1>
        <button
            onClick={() => fetchTrades(currentPage, activeFilters)}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:opacity-60"
        >
          {isLoading && trades.length > 0 ? <span className="spinner-small mr-2"></span> : null}
          Refresh
        </button>
      </div>

      <TradeFilters initialFilters={activeFilters} onApplyFilters={handleApplyFilters} />

      {error && (
        <div className="feedback-error my-4 text-center p-4">
          <p>{error}</p>
        </div>
      )}

      <TradesTable trades={trades} isLoading={isLoading && trades.length === 0} />
      <PaginationControls
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={handlePageChange}
        itemsPerPage={ITEMS_PER_PAGE}
        totalItems={totalTrades}
      />
    </div>
  );
}
```
