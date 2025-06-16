"use client";

import React, { useState, useEffect, FormEvent } from 'react';
import { formatISO, parseISO } from 'date-fns'; // For date handling

export interface TradeFilterValues {
  symbol?: string;
  order_id_search?: string; // Renamed from search_term in backend query to be more specific for this field
  start_time?: string; // ISO string (YYYY-MM-DDTHH:mm:ss.sssZ)
  end_time?: string;   // ISO string
  side?: 'BUY' | 'SELL' | ''; // Empty string for 'All'
  order_type?: string;
  status?: string;
}

interface TradeFiltersProps {
  initialFilters: TradeFilterValues;
  onApplyFilters: (filters: TradeFilterValues) => void;
}

const COMMON_ORDER_TYPES = ["MARKET", "LIMIT", "STOP_MARKET", "STOP_LOSS", "STOP_LOSS_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT", "TWAP", "GRID"];
const COMMON_STATUSES = ["NEW", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED", "EXPIRED"];

export default function TradeFilters({ initialFilters, onApplyFilters }: TradeFiltersProps) {
  const [filters, setFilters] = useState<TradeFilterValues>(initialFilters);

  useEffect(() => {
    setFilters(initialFilters);
  }, [initialFilters]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value || undefined })); // Set to undefined if empty for cleaner query params
  };

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target; // value is yyyy-MM-dd from date input
    if (value) {
      let isoValue = "";
      try {
        const dateObj = parseISO(value); // Parses "YYYY-MM-DD" to date object at UTC midnight
        if (name === 'start_time') {
            // Format to ISO string representing start of the day in UTC
            isoValue = formatISO(dateObj, { representation: 'complete' }).replace(/\+.*$/, 'Z');
        } else if (name === 'end_time') {
            // Format to ISO string representing end of the day in UTC
            const endOfDay = new Date(dateObj.getFullYear(), dateObj.getMonth(), dateObj.getDate(), 23, 59, 59, 999);
            isoValue = formatISO(endOfDay).replace(/\+.*$/, 'Z');
        }
         setFilters(prev => ({ ...prev, [name]: isoValue }));
      } catch (error) {
        console.error("Error parsing date:", error);
        setFilters(prev => ({ ...prev, [name]: undefined }));
      }
    } else {
      setFilters(prev => ({ ...prev, [name]: undefined }));
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    // Remove empty/undefined values before submitting for cleaner query params
    const cleanedFilters: TradeFilterValues = {};
    for (const [key, value] of Object.entries(filters)) {
        if (value !== '' && value !== undefined && value !== null) {
            cleanedFilters[key as keyof TradeFilterValues] = value;
        }
    }
    onApplyFilters(cleanedFilters);
  };

  const handleClearFilters = () => {
    const clearedFilters: TradeFilterValues = {}; // Empty object means all filters cleared
    setFilters(clearedFilters);
    onApplyFilters(clearedFilters);
  };

  const inputClass = "mt-1 block w-full px-3 py-2.5 bg-gray-700 border border-gray-600 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-white placeholder-gray-400";
  const labelClass = "block text-xs font-medium text-gray-400 mb-1";
  const buttonPrimaryClass = "w-full text-sm py-2.5 px-4 font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-md transition duration-150 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-800 disabled:opacity-60";
  const buttonSecondaryClass = "w-full text-sm py-2.5 px-4 font-semibold text-gray-300 bg-gray-600 hover:bg-gray-500 rounded-lg shadow-md transition duration-150 ease-in-out focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-800";


  return (
    <form onSubmit={handleSubmit} className="p-4 md:p-6 bg-gray-800 rounded-xl shadow-2xl mb-6 space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-3 items-end">
        <div>
          <label htmlFor="filter-symbol" className={labelClass}>Symbol</label>
          <input type="text" name="symbol" id="filter-symbol" value={filters.symbol || ''} onChange={handleChange}
                 className={inputClass} placeholder="e.g., BTCUSDT" />
        </div>
        <div>
          <label htmlFor="filter-order_id_search" className={labelClass}>Order ID (contains)</label>
          <input type="text" name="order_id_search" id="filter-order_id_search" value={filters.order_id_search || ''} onChange={handleChange}
                 className={inputClass} placeholder="Search Order ID" />
        </div>
        <div>
          <label htmlFor="filter-start_time" className={labelClass}>Start Date (UTC)</label>
          <input type="date" name="start_time" id="filter-start_time"
                 value={filters.start_time ? filters.start_time.substring(0,10) : ''}
                 onChange={handleDateChange} className={inputClass} />
        </div>
        <div>
          <label htmlFor="filter-end_time" className={labelClass}>End Date (UTC)</label>
          <input type="date" name="end_time" id="filter-end_time"
                 value={filters.end_time ? filters.end_time.substring(0,10) : ''}
                 onChange={handleDateChange} className={inputClass} />
        </div>
        <div>
          <label htmlFor="filter-side" className={labelClass}>Side</label>
          <select name="side" id="filter-side" value={filters.side || ''} onChange={handleChange} className={inputClass}>
            <option value="">All Sides</option>
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
        </div>
        <div>
          <label htmlFor="filter-order_type" className={labelClass}>Order Type</label>
          <select name="order_type" id="filter-order_type" value={filters.order_type || ''} onChange={handleChange} className={inputClass}>
            <option value="">All Types</option>
            {COMMON_ORDER_TYPES.map(type => <option key={type} value={type}>{type}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="filter-status" className={labelClass}>Status</label>
          <select name="status" id="filter-status" value={filters.status || ''} onChange={handleChange} className={inputClass}>
            <option value="">All Statuses</option>
            {COMMON_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="flex space-x-3 pt-3 sm:pt-0 sm:col-start-4 lg:col-start-auto"> {/* Align buttons */}
          <button type="submit" className={buttonPrimaryClass}>Apply Filters</button>
          <button type="button" onClick={handleClearFilters} className={buttonSecondaryClass}>Clear</button>
        </div>
      </div>
    </form>
  );
}
```
