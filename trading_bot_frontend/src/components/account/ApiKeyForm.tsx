"use client";

import React, { useState, useEffect, FormEvent } from 'react';
import { apiClient } from '@/lib/apiClient';
// Assuming UserAPIKeyResponse is similar to ApiKeyDisplay used in ApiKeyList
// and UserAPIKeyCreate/Update are defined in backend schemas and accessible or re-defined here.

// Define types based on backend schemas (user_api_key_schemas.py)
interface UserAPIKeyCreate {
  label?: string | null; // Optional in schema, default None
  binance_api_key: string;
  binance_api_secret: string;
  is_active: boolean;
}

interface UserAPIKeyUpdate {
  label?: string | null;
  is_active?: boolean | null;
}

interface UserAPIKeyResponse { // Matches UserAPIKeyResponse from schemas
  id: number;
  label: string | null;
  is_active: boolean;
  binance_api_key_preview: string;
  is_valid_on_binance: boolean;
  last_validated_at: string | null; // Dates as strings
  created_at: string;
  updated_at: string;
  user_id: string; // UUID as string
}


interface ApiKeyFormProps {
  apiKeyToEdit?: UserAPIKeyResponse | null; // Use the more complete type
  onFormSubmitSuccess: () => void;
  onCancel: () => void;
}

export default function ApiKeyForm({ apiKeyToEdit, onFormSubmitSuccess, onCancel }: ApiKeyFormProps) {
  const [label, setLabel] = useState('');
  const [binanceApiKey, setBinanceApiKey] = useState('');
  const [binanceApiSecret, setBinanceApiSecret] = useState('');
  const [isActive, setIsActive] = useState(true);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isEditing = Boolean(apiKeyToEdit);

  useEffect(() => {
    if (isEditing && apiKeyToEdit) {
      setLabel(apiKeyToEdit.label || '');
      setIsActive(apiKeyToEdit.is_active);
      setBinanceApiKey(''); // Clear sensitive fields when editing
      setBinanceApiSecret('');
    } else {
      // Reset for new form
      setLabel('');
      setBinanceApiKey('');
      setBinanceApiSecret('');
      setIsActive(true);
    }
    setErrorMessage(null); // Clear error when form opens or apiKeyToEdit changes
  }, [apiKeyToEdit, isEditing]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage(null);

    try {
      if (isEditing && apiKeyToEdit) {
        // Update existing key (only label and is_active)
        const payload: UserAPIKeyUpdate = {};
        if (label !== apiKeyToEdit.label) payload.label = label; // Only send if changed
        if (isActive !== apiKeyToEdit.is_active) payload.is_active = isActive;

        if (Object.keys(payload).length > 0) { // Only submit if there are actual changes
            await apiClient(`/users/api-keys/${apiKeyToEdit.id}`, {
                method: 'PUT',
                body: payload,
            });
        } else {
            // No changes to submit, can treat as success or inform user
            console.log("No changes detected for API Key update.");
        }
      } else {
        // Create new key
        if (!binanceApiKey.trim() || !binanceApiSecret.trim()) {
          setErrorMessage("Binance API Key and Secret are required for new entries.");
          setIsLoading(false);
          return;
        }
        const payload: UserAPIKeyCreate = {
          label: label.trim() || undefined, // Send undefined if empty to let backend handle default/null
          binance_api_key: binanceApiKey,
          binance_api_secret: binanceApiSecret,
          is_active: isActive,
        };
        await apiClient('/users/api-keys', {
          method: 'POST',
          body: payload,
        });
      }
      onFormSubmitSuccess(); // Trigger refresh and close modal
    } catch (err: any) {
      console.error("API Key form submission error:", err);
      setErrorMessage(err.data?.detail || err.message || "An error occurred while saving the API key.");
    } finally {
      setIsLoading(false);
    }
  };

  const inputClass = "mt-1 block w-full px-3 py-2.5 bg-gray-700 border border-gray-600 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-white placeholder-gray-400";
  const labelClass = "block text-sm font-medium text-gray-300";

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 backdrop-blur-md flex items-center justify-center p-4 z-50 transition-opacity duration-150 ease-in-out">
      <div className="bg-gray-800 p-6 sm:p-8 rounded-xl shadow-2xl w-full max-w-lg space-y-5 transform transition-all duration-150 ease-in-out scale-100 ring-1 ring-gray-700/50">
        <div className="flex justify-between items-center">
           <h2 className="text-2xl font-semibold text-white">{isEditing ? 'Edit API Key' : 'Add New API Key'}</h2>
           <button onClick={onCancel} className="text-gray-500 hover:text-gray-300 transition-colors p-1 rounded-full hover:bg-gray-700">
             <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
           </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="label" className={labelClass}>Label <span className="text-xs text-gray-500">(Optional, for your reference)</span></label>
            <input type="text" name="label" id="label" value={label} onChange={(e) => setLabel(e.target.value)}
                   className={inputClass} placeholder="e.g., My Main Trading Account" />
          </div>
          {!isEditing && (
            <>
              <div>
                <label htmlFor="apiKey" className={labelClass}>Binance API Key <span className="text-red-400">*</span></label>
                <input type="password" name="apiKey" id="apiKey" value={binanceApiKey} onChange={(e) => setBinanceApiKey(e.target.value)}
                       className={inputClass} placeholder="Enter your Binance API Key" required={!isEditing} />
              </div>
              <div>
                <label htmlFor="apiSecret" className={labelClass}>Binance API Secret <span className="text-red-400">*</span></label>
                <input type="password" name="apiSecret" id="apiSecret" value={binanceApiSecret} onChange={(e) => setBinanceApiSecret(e.target.value)}
                       className={inputClass} placeholder="Enter your Binance API Secret" required={!isEditing} />
              </div>
            </>
          )}
          <div className="flex items-center pt-2">
            <input id="isActive" name="isActive" type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)}
                   className="h-4 w-4 text-indigo-500 border-gray-600 rounded bg-gray-700 focus:ring-indigo-500 focus:ring-offset-gray-800" />
            <label htmlFor="isActive" className="ml-3 block text-sm text-gray-300">Set as active key</label>
          </div>

          {errorMessage && <p className="feedback-error">{errorMessage}</p>}

          <div className="flex items-center justify-end space-x-4 pt-3">
            <button type="button" onClick={onCancel}
                    className="px-5 py-2.5 text-sm font-medium text-gray-300 bg-gray-600 hover:bg-gray-500 rounded-lg transition duration-150 ease-in-out focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-800">
              Cancel
            </button>
            <button type="submit" disabled={isLoading}
                    className="px-5 py-2.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50 transition duration-150 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-800">
              {isLoading ? (isEditing ? 'Saving...' : 'Adding...') : (isEditing ? 'Save Changes' : 'Add API Key')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

```
