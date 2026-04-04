import api from './api';

export const cacheService = {
  getConfig: () => api.get('/cache/config').then(r => r.data),
  updateConfig: (body) => api.put('/cache/config', body).then(r => r.data),
  getStats: () => api.get('/cache/stats').then(r => r.data),
  clear: () => api.delete('/cache/clear').then(r => r.data),
};
