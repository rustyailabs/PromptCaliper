import api from './api';

export const logService = {
  getLogs: (params = {}) => api.get('/logs', { params }).then(r => r.data),
  getLog: (id) => api.get(`/logs/${id}`).then(r => r.data),
  getStats: (hours = 24) => api.get('/logs/stats', { params: { hours } }).then(r => r.data),
};
