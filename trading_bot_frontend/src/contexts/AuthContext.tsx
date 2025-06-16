"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { useRouter } from 'next/navigation';
// Removed useWebSocket from here, it will be used by components that need direct WS interaction
// AuthContext will only control the 'isAuthenticated' flag which components can use for 'shouldConnect'

// Re-export Balance from here if it's a central type for auth-related data, or keep it in useWebSocket.ts
// For this example, assuming components will import Balance from useWebSocket if needed.
// export interface Balance { asset: string; free: string; locked: string; }


interface AuthContextType {
  isAuthenticated: boolean;
  username: string | null;
  login: (user: string, pass: string) => Promise<boolean>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  // WebSocket connection is NOT directly managed by AuthContext anymore.
  // Components will use the useWebSocket hook and pass `isAuthenticated` to `shouldConnect`.
  // This simplifies AuthContext and makes WebSocket usage more explicit in components.

  useEffect(() => {
    const storedUser = localStorage.getItem('tradingBotUser');
    const storedCreds = localStorage.getItem('tradingBotCredentials'); // Check if credentials exist
    if (storedUser && storedCreds) { // User is "logged in" if both user and creds are stored
      setUsername(storedUser);
      setIsAuthenticated(true);
    }
    setIsLoading(false);
  }, []);

  const login = async (user: string, pass: string): Promise<boolean> => {
    setIsLoading(true);
    try {
      const headers = new Headers();
      headers.append('Authorization', 'Basic ' + btoa(user + ":" + pass));
      // Ensure NEXT_PUBLIC_API_URL is defined or defaults correctly
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBaseUrl}/users/me`, { method: 'GET', headers });

      if (response.ok) {
        const data = await response.json();
        setUsername(data.username);
        setIsAuthenticated(true);
        localStorage.setItem('tradingBotUser', data.username);
        localStorage.setItem('tradingBotCredentials', btoa(user + ":" + pass));
        router.push('/dashboard');
        setIsLoading(false);
        return true;
      } else {
        console.error('Login failed:', response.status);
        setIsAuthenticated(false); setUsername(null);
        localStorage.removeItem('tradingBotUser'); localStorage.removeItem('tradingBotCredentials');
        setIsLoading(false); return false;
      }
    } catch (error) {
      console.error('Login error:', error);
      setIsAuthenticated(false); setUsername(null);
      localStorage.removeItem('tradingBotUser'); localStorage.removeItem('tradingBotCredentials');
      setIsLoading(false); return false;
    }
  };

  const logout = useCallback(() => {
    setIsAuthenticated(false);
    setUsername(null);
    localStorage.removeItem('tradingBotUser');
    localStorage.removeItem('tradingBotCredentials');
    router.push('/login');
  }, [router]);

  return (
    <AuthContext.Provider value={{ isAuthenticated, username, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
