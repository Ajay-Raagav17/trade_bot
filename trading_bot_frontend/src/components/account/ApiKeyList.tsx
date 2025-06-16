"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/apiClient';

// Assuming this matches the UserAPIKeyResponse schema from the backend
interface ApiKeyDisplay {
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

// For the response from the /validate endpoint
interface ApiKeyValidationResponse extends ApiKeyDisplay {}


interface ApiKeyListProps {
  onEditRequest: (apiKey: ApiKeyDisplay) => void;
  onActionFeedback: (type: 'success' | 'error', message: string) => void;
  refreshTrigger: number;
  doRefresh: () => void;
}

export default function ApiKeyList({ onEditRequest, onActionFeedback, refreshTrigger, doRefresh }: ApiKeyListProps) {
  const [apiKeys, setApiKeys] = useState<ApiKeyDisplay[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // State to track loading status for individual key actions
  const [actionLoading, setActionLoading] = useState<{[keyAction: string]: boolean}>({}); // e.g., { 'delete-5': true, 'validate-5': true }


  const fetchApiKeys = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient<ApiKeyDisplay[]>('/users/api-keys');
      setApiKeys(data || []);
    } catch (err: any) {
      console.error("Failed to fetch API keys:", err);
      setError(err.data?.detail || err.message || "Could not load your API keys at this time.");
      setApiKeys([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApiKeys();
  }, [fetchApiKeys, refreshTrigger]);

  const handleDelete = async (keyId: number) => {
    if (!window.confirm('Are you sure you want to delete this API key? This action cannot be undone.')) return;

    setActionLoading(prev => ({ ...prev, [`delete-${keyId}`]: true }));
    try {
      await apiClient(`/users/api-keys/${keyId}`, { method: 'DELETE' });
      onActionFeedback('success', `API Key (ID: ${keyId}) deleted successfully.`);
      doRefresh(); // Trigger list refresh from parent
    } catch (err: any) {
      console.error(`Failed to delete API key ${keyId}:`, err);
      onActionFeedback('error', err.data?.detail || err.message || 'Failed to delete API key.');
    } finally {
      setActionLoading(prev => ({ ...prev, [`delete-${keyId}`]: false }));
    }
  };

  const handleValidate = async (keyId: number) => {
    setActionLoading(prev => ({ ...prev, [`validate-${keyId}`]: true }));
    try {
      const response = await apiClient<ApiKeyValidationResponse>(`/users/api-keys/${keyId}/validate`, { method: 'POST' });
      const validationStatus = response.is_valid_on_binance ? 'valid' : 'invalid';
      const lastValidated = response.last_validated_at ? new Date(response.last_validated_at).toLocaleString() : 'N/A';
      onActionFeedback('success', `API Key (ID: ${keyId}) validation status: ${validationStatus}. Last checked: ${lastValidated}`);
      doRefresh(); // Trigger list refresh to show updated status
    } catch (err: any) {
      console.error(`Failed to validate API key ${keyId}:`, err);
      onActionFeedback('error', err.data?.detail || err.message || `Failed to validate API key ${keyId}.`);
    } finally {
      setActionLoading(prev => ({ ...prev, [`validate-${keyId}`]: false }));
    }
  };


  if (isLoading) {
    return (
      <div className="text-center py-10 bg-gray-800 shadow-xl rounded-lg">
        <div className="flex justify-center items-center">
          <div className="spinner mr-3"></div>
          <p className="text-indigo-300">Loading API Keys...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return <div className="feedback-error my-4"><p>{error}</p></div>;
  }

  if (apiKeys.length === 0) {
    return (
      <div className="text-center py-16 bg-gray-800 shadow-xl rounded-lg">
        <svg className="mx-auto h-12 w-12 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
        </svg>
        <h3 className="mt-2 text-lg font-medium text-gray-300">No API keys found.</h3>
        <p className="mt-1 text-sm text-gray-500">Get started by adding a new Binance API key.</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 shadow-xl rounded-lg overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-700">
        <thead className="bg-gray-750">
          <tr>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-indigo-300 uppercase tracking-wider">Label</th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-indigo-300 uppercase tracking-wider">Key Preview</th>
            <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-indigo-300 uppercase tracking-wider">Active</th>
            <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-indigo-300 uppercase tracking-wider">Validated</th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-indigo-300 uppercase tracking-wider">Last Validated</th>
            <th scope="col" className="px-6 py-4 text-right text-xs font-medium text-indigo-300 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="bg-gray-800 divide-y divide-gray-700">
          {apiKeys.map((key) => (
            <tr key={key.id} className="hover:bg-gray-700/50 transition-colors duration-150">
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-white">{key.label || <span className="text-gray-500 italic">No Label</span>}</td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300 font-mono">{key.binance_api_key_preview}</td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-center">
                <span className={`px-2.5 py-0.5 inline-flex text-xs leading-5 font-semibold rounded-full ${
                  key.is_active ? 'bg-green-600 text-green-200' : 'bg-gray-600 text-gray-300'
                }`}>
                  {key.is_active ? 'YES' : 'NO'}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-center">
                <span className={`px-2.5 py-0.5 inline-flex text-xs leading-5 font-semibold rounded-full ${
                  key.is_valid_on_binance ? 'bg-green-600 text-green-200' : 'bg-red-600 text-red-200'
                }`}>
                  {key.is_valid_on_binance ? 'Valid' : 'Invalid/Untested'}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                {key.last_validated_at ? new Date(key.last_validated_at).toLocaleString() : <span className="italic">Never</span>}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-3">
                <button
                  onClick={() => onEditRequest(key)}
                  disabled={actionLoading[`edit-${key.id}`] || actionLoading[`validate-${key.id}`] || actionLoading[`delete-${key.id}`]}
                  className="text-indigo-400 hover:text-indigo-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Edit Key Label/Status"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleValidate(key.id)}
                  disabled={actionLoading[`validate-${key.id}`] || actionLoading[`delete-${key.id}`]}
                  className="text-blue-400 hover:text-blue-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Validate Key with Binance"
                >
                  {actionLoading[`validate-${key.id}`] ? <span className="spinner-small"></span> : 'Validate'}
                </button>
                <button
                  onClick={() => handleDelete(key.id)}
                  disabled={actionLoading[`delete-${key.id}`] || actionLoading[`validate-${key.id}`]}
                  className="text-red-400 hover:text-red-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Delete Key"
                >
                  {actionLoading[`delete-${key.id}`] ? <span className="spinner-small"></span> : 'Delete'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Add .spinner-small to globals.css if needed, or use a shared spinner component
// For now, assuming .spinner can be sized with text-sm or similar.
// If spinner is too big, a spinner-small class would be:
// .spinner-small { border-width: 2px; width: 0.8em; height: 0.8em; margin-right: 0.4em; }
```
