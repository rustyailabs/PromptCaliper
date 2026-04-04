import api from './api';

export const rateLimitService = {
  listPolicies: () => api.get('/rate-limits').then(r => r.data),
  createPolicy: (body) => api.post('/rate-limits', body).then(r => r.data),
  updatePolicy: (id, body) => api.patch(`/rate-limits/${id}`, body).then(r => r.data),
  deletePolicy: (id) => api.delete(`/rate-limits/${id}`),
  getCurrentUsage: () => api.get('/rate-limits/current-usage').then(r => r.data),
};
