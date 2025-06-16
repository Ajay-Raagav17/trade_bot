"use client";

import React, { useEffect } from 'react';
import TwapForm from '@/components/strategies/TwapForm';
import GridForm from '@/components/strategies/GridForm';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';

export default function StrategiesPage() {
  const { isAuthenticated, isLoading: authIsLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!authIsLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, authIsLoading, router]);

  if (authIsLoading || (!isAuthenticated && !authIsLoading)) {
    return <div className="flex items-center justify-center min-h-[calc(100vh-200px)]"><p className="text-lg text-gray-400">Loading strategies interface...</p></div>;
  }

  return (
    <div className="space-y-12"> {/* Increased main spacing */}
      <h1 className="text-3xl font-bold text-white mb-10 text-center">Automated Trading Strategies</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start"> {/* Increased gap, align items start */}
        <section id="twap-section" className="w-full"> {/* Ensure sections take full width in their grid cell */}
          <TwapForm />
        </section>

        <section id="grid-section" className="w-full">
          <GridForm />
        </section>
      </div>
    </div>
  );
}
