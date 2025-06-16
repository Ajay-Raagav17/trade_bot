"use client";

import React from 'react';

interface PaginationControlsProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  itemsPerPage?: number;
  totalItems?: number;
}

export default function PaginationControls({
  currentPage,
  totalPages,
  onPageChange,
  itemsPerPage, // Currently not used in display string, but available
  totalItems    // Currently not used in display string, but available
}: PaginationControlsProps) {
  if (totalPages <= 1) {
    return null;
  }

  const handlePrevious = () => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  };

  // Generate page numbers with ellipsis
  // Max 7 page numbers to show: current, 2 before, 2 after, first, last, and ellipsis
  const pageNumbers = [];
  const maxPagesToShow = 7; // Includes first, last, current, and two on each side + potential ellipsis
  const sidePages = 2; // Number of pages to show on each side of current page

  if (totalPages <= maxPagesToShow) {
    for (let i = 1; i <= totalPages; i++) {
      pageNumbers.push(i);
    }
  } else {
    pageNumbers.push(1); // Always show first page
    if (currentPage > sidePages + 2) {
      pageNumbers.push('...'); // Ellipsis after first page
    }

    let startPage = Math.max(2, currentPage - sidePages);
    let endPage = Math.min(totalPages - 1, currentPage + sidePages);

    if (currentPage <= sidePages + 1) {
        endPage = Math.min(totalPages - 1, maxPagesToShow - 2); // Adjust end page if current is near start
    }
    if (currentPage >= totalPages - sidePages) {
        startPage = Math.max(2, totalPages - maxPagesToShow + 3); // Adjust start page if current is near end
    }

    for (let i = startPage; i <= endPage; i++) {
      pageNumbers.push(i);
    }

    if (currentPage < totalPages - sidePages - 1) {
      pageNumbers.push('...'); // Ellipsis before last page
    }
    pageNumbers.push(totalPages); // Always show last page
  }


  return (
    <div className="flex items-center justify-between mt-6 px-4 py-3 sm:px-6 bg-gray-800 border-t border-gray-700 rounded-b-lg shadow">
      {/* Mobile: Simple Prev/Next */}
      <div className="flex-1 flex justify-between sm:hidden">
        <button
          onClick={handlePrevious}
          disabled={currentPage === 1}
          className="relative inline-flex items-center px-4 py-2 border border-gray-600 text-sm font-medium rounded-md text-gray-300 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Previous
        </button>
        <button
          onClick={handleNext}
          disabled={currentPage === totalPages}
          className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-600 text-sm font-medium rounded-md text-gray-300 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>

      {/* Desktop: Detailed Pagination */}
      <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-gray-400">
            Page <span className="font-medium text-indigo-300">{currentPage}</span> of <span className="font-medium text-indigo-300">{totalPages}</span>
            {totalItems !== undefined && (
                <span className="ml-2">
                    (<span className="font-medium">{totalItems}</span> results)
                </span>
            )}
          </p>
        </div>
        <div>
          <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
            <button
              onClick={handlePrevious}
              disabled={currentPage === 1}
              className="relative inline-flex items-center px-3 py-2 rounded-l-md border border-gray-600 bg-gray-700 text-sm font-medium text-gray-300 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Previous"
            >
              &lt;
            </button>

            {pageNumbers.map((page, index) =>
              typeof page === 'number' ? (
                <button
                  key={index}
                  onClick={() => onPageChange(page)}
                  aria-current={currentPage === page ? 'page' : undefined}
                  className={`relative inline-flex items-center px-4 py-2 border border-gray-600 text-sm font-medium
                    ${currentPage === page
                      ? 'z-10 bg-indigo-600 text-white ring-1 ring-indigo-500'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }
                    disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {page}
                </button>
              ) : (
                <span key={index} className="relative inline-flex items-center px-4 py-2 border border-gray-600 bg-gray-700 text-sm font-medium text-gray-400">
                  {page}
                </span>
              )
            )}

            <button
              onClick={handleNext}
              disabled={currentPage === totalPages}
              className="relative inline-flex items-center px-3 py-2 rounded-r-md border border-gray-600 bg-gray-700 text-sm font-medium text-gray-300 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Next"
            >
              &gt;
            </button>
          </nav>
        </div>
      </div>
    </div>
  );
}
```
