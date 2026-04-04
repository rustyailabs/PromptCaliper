import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('ft_access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Global refresh lock ───────────────────────────────────────────────────────
// Ensures that when multiple concurrent requests all receive a 401, only ONE
// token-refresh call is made. The others wait for that single Promise to resolve
// and then retry with the new token — preventing a refresh-token rotation storm
// that would log the user out unexpectedly.
let _refreshPromise = null;

async function _refreshTokens() {
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = (async () => {
    try {
      const refreshToken = localStorage.getItem('ft_refresh_token');
      if (!refreshToken) throw new Error('No refresh token');
      const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
        refresh_token: refreshToken,
      });
      localStorage.setItem('ft_access_token', data.access_token);
      localStorage.setItem('ft_refresh_token', data.refresh_token);
      return data.access_token;
    } catch (err) {
      // Refresh failed — clear tokens and force logout
      localStorage.removeItem('ft_access_token');
      localStorage.removeItem('ft_refresh_token');
      window.dispatchEvent(new CustomEvent('ft:logout'));
      throw err;
    } finally {
      _refreshPromise = null;
    }
  })();

  return _refreshPromise;
}

// On 401: attempt silent refresh via the global lock, then retry once
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retried) {
      original._retried = true;
      try {
        const newAccessToken = await _refreshTokens();
        original.headers.Authorization = `Bearer ${newAccessToken}`;
        return api(original);
      } catch {
        // _refreshTokens already dispatched ft:logout and cleared storage
      }
    }
    return Promise.reject(error);
  }
);

export default api;
