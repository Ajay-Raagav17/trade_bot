"use client";

import React, { ReactNode } from 'react';
import { AuthProvider } from '@/contexts/AuthContext';
import Header from '@/components/layout/Header';
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"] }); // Ensure Inter font is loaded here

export default function RootClientLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      {/* Apply className here to ensure font is applied within AuthProvider context */}
      <div className={`min-h-screen flex flex-col ${inter.className}`}>
        <Header />
        <main className="flex-grow container mx-auto p-4 sm:p-6 lg:p-8">
          {children}
        </main>
        <footer className="bg-gray-800 text-white p-4 text-center text-sm">
          © 2024 Trading Bot App
        </footer>
      </div>
    </AuthProvider>
  );
}
