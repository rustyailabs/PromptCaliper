import api from './api';

export const budgetService = {
  listPolicies: () => api.get('/budgets').then(r => r.data),
  createPolicy: (body) => api.post('/budgets', body).then(r => r.data),
  updatePolicy: (id, body) => api.patch(`/budgets/${id}`, body).then(r => r.data),
  deletePolicy: (id) => api.delete(`/budgets/${id}`),
  getSummary: (period) => api.get('/budgets/summary', { params: { period } }).then(r => r.data),
  getSpendByTeam: (period) => api.get('/budgets/spend/by-team', { params: { period } }).then(r => r.data),
  getSpendByModel: (period) => api.get('/budgets/spend/by-model', { params: { period } }).then(r => r.data),
  getSpendByKey: (period) => api.get('/budgets/spend/by-key', { params: { period } }).then(r => r.data),
  getTimeseries: (days, granularity) => api.get('/budgets/spend/timeseries', { params: { days, granularity } }).then(r => r.data),
};
