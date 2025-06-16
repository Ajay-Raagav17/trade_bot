"use client";

import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

export default function Header() {
  const { isAuthenticated, username, logout, isLoading } = useAuth();

  return (
    <header className="bg-gray-800 text-white p-4 shadow-md">
      <nav className="container mx-auto flex justify-between items-center">
        <Link href="/" className="text-xl font-bold text-white hover:text-brand-primary transition-colors duration-150 ease-in-out">
          Trading Bot
        </Link>
        <div className="space-x-4 flex items-center">
          <Link href="/dashboard" className="text-gray-300 hover:text-brand-primary transition-colors duration-150 ease-in-out">
            Dashboard
          </Link>
          <Link href="/trading" className="text-gray-300 hover:text-brand-primary transition-colors duration-150 ease-in-out">
            Trading
          </Link>
          <Link href="/strategies" className="text-gray-300 hover:text-brand-primary transition-colors duration-150 ease-in-out">
            Strategies
          </Link>

          {isLoading ? (
            <span className="text-sm text-gray-400 px-4">Loading...</span> /* Added padding */
          ) : isAuthenticated ? (
            <>
              <span className="text-sm hidden sm:inline">Welcome, {username}</span>
              <button
                onClick={logout}
                className="bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded-lg text-sm transition-all duration-150 ease-in-out"
              >
                Logout
              </button>
            </>
          ) : (
            <Link href="/login" className="bg-brand-primary hover:bg-opacity-80 text-white font-semibold py-2 px-4 rounded-lg text-sm transition-all duration-150 ease-in-out">
              Login
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
