import api from './api';

export const guardrailService = {
  list: () => api.get('/guardrails').then(r => r.data),
  create: (body) => api.post('/guardrails', body).then(r => r.data),
  update: (id, body) => api.patch(`/guardrails/${id}`, body).then(r => r.data),
  delete: (id) => api.delete(`/guardrails/${id}`),
  test: (body) => api.post('/guardrails/test', body).then(r => r.data),
};
