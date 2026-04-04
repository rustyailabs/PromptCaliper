import api from './api';

export const teamService = {
  list: () => api.get('/teams').then(r => r.data),
  create: (body) => api.post('/teams', body).then(r => r.data),
  get: (id) => api.get(`/teams/${id}`).then(r => r.data),
  update: (id, body) => api.patch(`/teams/${id}`, body).then(r => r.data),
  delete: (id) => api.delete(`/teams/${id}`),
  getSpend: (id, period) => api.get(`/budgets/spend/by-team`, { params: { period } }).then(r => r.data),
};
