"use client";

import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import ApiKeyList from '@/components/account/ApiKeyList';
import ApiKeyForm from '@/components/account/ApiKeyForm';

// Define type for API key data passed around, based on UserAPIKeyResponse schema
interface ApiKeyDisplayData {
  id: number;
  label: string | null;
  is_active: boolean;
  binance_api_key_preview: string;
  is_valid_on_binance: boolean;
  last_validated_at: string | null;
  created_at: string;
  updated_at: string;
  user_id: string;
}

export default function ApiKeysPage() {
  const { isAuthenticated, isLoading: authIsLoading } = useAuth();
  const router = useRouter();

  const [showApiKeyForm, setShowApiKeyForm] = useState(false);
  const [editingApiKey, setEditingApiKey] = useState<ApiKeyDisplayData | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [feedback, setFeedback] = useState<{type: 'success' | 'error', message: string} | null>(null);

  useEffect(() => {
    if (!authIsLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, authIsLoading, router]);

  const triggerRefresh = useCallback(() => {
    setRefreshTrigger(prev => prev + 1);
  }, []);

  const handleOpenForm = useCallback((apiKey: ApiKeyDisplayData | null = null) => {
    setEditingApiKey(apiKey);
    setShowApiKeyForm(true);
    setFeedback(null); // Clear previous feedback when opening form
  }, []);

  const handleFormSuccess = useCallback(() => {
    setShowApiKeyForm(false);
    setEditingApiKey(null);
    triggerRefresh();
    // Feedback message is now set by handleActionFeedback from ApiKeyList for delete/validate,
    // or directly in ApiKeyForm for add/update success.
    // For add/update, ApiKeyForm calls this onFormSubmitSuccess.
    // We can set a generic success message here if ApiKeyForm doesn't set one.
    setFeedback({type: 'success', message: editingApiKey ? 'API Key updated successfully.' : 'API Key added successfully.'});
    setTimeout(() => setFeedback(null), 5000); // Auto-dismiss
  }, [triggerRefresh, editingApiKey]);

  const handleCancelForm = useCallback(() => {
    setShowApiKeyForm(false);
    setEditingApiKey(null);
  }, []);

  const handleActionFeedback = useCallback((type: 'success' | 'error', message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 5000); // Auto-dismiss feedback
  }, []);


  if (authIsLoading || (!isAuthenticated && !authIsLoading)) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-200px)]">
        <div className="spinner mr-3"></div>
        <p className="text-lg text-gray-400">Loading API Key Management...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
        <h1 className="text-2xl sm:text-3xl font-bold text-white">Manage Binance API Keys</h1>
        <button
          onClick={() => handleOpenForm(null)} // Pass null for new key
          className="px-5 py-2.5 font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-md transition duration-150 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-900"
        >
          Add New API Key
        </button>
      </div>

      {feedback && (
        <div className={`p-4 mb-4 rounded-md text-sm ${feedback.type === 'success' ? 'bg-green-800 text-green-200 border border-green-700' : 'bg-red-800 text-red-200 border border-red-700'}`}>
          {feedback.message}
        </div>
      )}

      {showApiKeyForm && (
        <ApiKeyForm
          apiKeyToEdit={editingApiKey}
          onFormSubmitSuccess={handleFormSuccess}
          onCancel={handleCancelForm}
        />
      )}

      <ApiKeyList
        onEditRequest={handleOpenForm}
        onActionFeedback={handleActionFeedback}
        refreshTrigger={refreshTrigger}
        doRefresh={triggerRefresh}
      />
    </div>
  );
}
```
