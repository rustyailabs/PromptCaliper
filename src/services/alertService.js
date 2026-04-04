import api from './api';

export const alertService = {
  listRules: () => api.get('/alerts/rules').then(r => r.data),
  createRule: (body) => api.post('/alerts/rules', body).then(r => r.data),
  updateRule: (id, body) => api.patch(`/alerts/rules/${id}`, body).then(r => r.data),
  deleteRule: (id) => api.delete(`/alerts/rules/${id}`),
  getHistory: (params = {}) => api.get('/alerts/history', { params }).then(r => r.data),
};
