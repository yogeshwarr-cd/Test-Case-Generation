const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
).replace(/\/$/, '');

function buildUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

function getHeaders(isMultipart = false): HeadersInit {
  const headers: Record<string, string> = {};
  if (!isMultipart) {
    headers['Content-Type'] = 'application/json';
  }
  
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('auth_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }
  return headers;
}

async function handleResponse(response: Response, requestUrl: string) {
  if (!response.ok) {
    const responseBody = await response.text();
    let errorMsg = responseBody || response.statusText || 'An error occurred';
    try {
      const errData = JSON.parse(responseBody);
      errorMsg = errData.message || errData.detail || JSON.stringify(errData);
    } catch {
      // Keep the plain-text backend response.
    }
    // Expected HTTP failures are surfaced by the page UI. Using console.error here
    // makes Next.js display a development error overlay even though the exception is
    // handled by the caller.
    console.warn(
      `Backend request failed: ${response.status} ${response.statusText} (${requestUrl})`
    );
    throw new Error(
      `Backend request failed (${response.status}) for ${requestUrl}: ${errorMsg}`
    );
  }
  return response.json();
}

export const apiClient = {
  get: async (url: string, options?: RequestInit) => {
    const requestUrl = buildUrl(url);
    const response = await fetch(requestUrl, {
      method: 'GET',
      headers: getHeaders(),
      ...options,
    });
    return handleResponse(response, requestUrl);
  },

  post: async (url: string, data?: unknown, options?: RequestInit) => {
    const requestUrl = buildUrl(url);
    const response = await fetch(requestUrl, {
      method: 'POST',
      headers: getHeaders(),
      body: data !== undefined ? JSON.stringify(data) : undefined,
      ...options,
    });
    return handleResponse(response, requestUrl);
  },

  patch: async (url: string, data?: unknown, options?: RequestInit) => {
    const requestUrl = buildUrl(url);
    const response = await fetch(requestUrl, {
      method: 'PATCH',
      headers: getHeaders(),
      body: data !== undefined ? JSON.stringify(data) : undefined,
      ...options,
    });
    return handleResponse(response, requestUrl);
  },

  postMultipart: async (url: string, formData: FormData, options?: RequestInit) => {
    const requestUrl = buildUrl(url);
    const headers = new Headers(getHeaders(true));
    new Headers(options?.headers).forEach((value, key) => headers.set(key, value));
    // The browser must add Content-Type with the generated multipart boundary.
    headers.delete('Content-Type');

    try {
      const response = await fetch(requestUrl, {
        ...options,
        method: 'POST',
        headers,
        body: formData,
      });
      return handleResponse(response, requestUrl);
    } catch (error) {
      if (error instanceof Error && error.message.startsWith('Backend request failed')) {
        throw error;
      }

      const mixedContent =
        typeof window !== 'undefined' &&
        window.location.protocol === 'https:' &&
        requestUrl.startsWith('http:');
      const reason = mixedContent
        ? 'The browser blocked mixed HTTP/HTTPS content.'
        : 'Check that FastAPI is running and that CORS allows the frontend origin.';
      console.error('Multipart network request failed', {
        url: requestUrl,
        error,
        mixedContent,
      });
      throw new Error(`Network request failed for ${requestUrl}. ${reason}`);
    }
  }
};
