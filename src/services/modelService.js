import api from './api';

export const modelService = {
  list: () => api.get('/models').then(r => r.data),
  create: (body) => api.post('/models', body).then(r => r.data),
  get: (id) => api.get(`/models/${id}`).then(r => r.data),
  update: (id, body) => api.patch(`/models/${id}`, body).then(r => r.data),
  delete: (id) => api.delete(`/models/${id}`),
};
