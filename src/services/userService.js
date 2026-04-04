import api from './api';

export const userService = {
  list: () => api.get('/users').then(r => r.data),
  create: (body) => api.post('/users', body).then(r => r.data),
  get: (id) => api.get(`/users/${id}`).then(r => r.data),
  update: (id, body) => api.patch(`/users/${id}`, body).then(r => r.data),
  delete: (id) => api.delete(`/users/${id}`),
};
