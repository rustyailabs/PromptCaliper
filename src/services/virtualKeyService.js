import api from './api';

export const virtualKeyService = {
  list: (params = {}) => api.get('/virtual-keys', { params }).then(r => r.data),
  create: (body) => api.post('/virtual-keys', body).then(r => r.data),
  get: (id) => api.get(`/virtual-keys/${id}`).then(r => r.data),
  update: (id, body) => api.patch(`/virtual-keys/${id}`, body).then(r => r.data),
  delete: (id) => api.delete(`/virtual-keys/${id}`),
  rotate: (id) => api.post(`/virtual-keys/${id}/rotate`).then(r => r.data),
  getSpend: (id) => api.get(`/virtual-keys/${id}/spend`).then(r => r.data),
};
