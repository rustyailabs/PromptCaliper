import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export const authService = {
  async login(username, password) {
    const { data } = await axios.post(`${BASE_URL}/auth/login`, { username, password });
    localStorage.setItem('ft_access_token', data.access_token);
    localStorage.setItem('ft_refresh_token', data.refresh_token);
    return data;
  },

  async logout() {
    const refreshToken = localStorage.getItem('ft_refresh_token');
    try {
      if (refreshToken) {
        await axios.post(
          `${BASE_URL}/auth/logout`,
          { refresh_token: refreshToken },
          { headers: { Authorization: `Bearer ${localStorage.getItem('ft_access_token')}` } }
        );
      }
    } finally {
      localStorage.removeItem('ft_access_token');
      localStorage.removeItem('ft_refresh_token');
    }
  },

  async getMe() {
    const token = localStorage.getItem('ft_access_token');
    if (!token) return null;
    const { data } = await axios.get(`${BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return data;
  },
};
