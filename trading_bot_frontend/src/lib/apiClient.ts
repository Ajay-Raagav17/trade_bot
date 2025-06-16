// Basic API client to interact with the backend

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ApiClientOptions extends RequestInit {
  includeAuth?: boolean;
}

export async function apiClient<T = any>(
  endpoint: string,
  options: ApiClientOptions = {}
): Promise<T> {
  const { includeAuth = true, ...fetchOptions } = options;
  const headers = new Headers(fetchOptions.headers || {});

  if (includeAuth) {
    // Ensure this code only runs on the client-side for localStorage access
    if (typeof window !== 'undefined') {
      const storedCredentials = localStorage.getItem('tradingBotCredentials');
      if (storedCredentials) {
        headers.append('Authorization', 'Basic ' + storedCredentials);
      } else {
        console.warn('API call made with includeAuth=true but no credentials found in localStorage.');
      }
    } else {
      // Handling server-side rendering or pre-rendering scenarios
      // Auth headers requiring localStorage cannot be added here.
      // This might mean certain API calls should only be made client-side,
      // or an alternative auth mechanism for SSR (like httpOnly cookies) is needed.
      console.warn('apiClient: includeAuth=true but localStorage is not available (server-side).');
    }
  }

  if (fetchOptions.body && typeof fetchOptions.body === 'object' && !(fetchOptions.body instanceof FormData)) {
    headers.append('Content-Type', 'application/json');
    fetchOptions.body = JSON.stringify(fetchOptions.body);
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...fetchOptions,
    headers,
  });

  if (!response.ok) {
    let errorData;
    try {
      errorData = await response.json();
    } catch (e) {
      // If response is not JSON or empty
      errorData = { detail: response.statusText || `Request failed with status ${response.status}` };
    }
    const error = new Error(errorData.detail || `API Error: ${response.status} ${response.statusText}`);
    (error as any).response = response;
    (error as any).data = errorData; // Attach parsed error data if available
    (error as any).status = response.status; // Attach status code
    throw error;
  }

  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
