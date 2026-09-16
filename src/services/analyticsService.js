import api from './api';

export const analyticsService = {
  getOverview: (timeRange = '24h') => api.get('/analytics/overview', { params: { time_range: timeRange } }).then(r => r.data),
  getTimeseries: (timeRange = '24h', granularity = 'hour') => api.get('/analytics/timeseries', { params: { time_range: timeRange, granularity } }).then(r => r.data),
  getModelDistribution: (timeRange = '24h') => api.get('/analytics/model-distribution', { params: { time_range: timeRange } }).then(r => r.data),
  getTeamSpendHistory: (months = 6) => api.get('/analytics/team-spend', { params: { months } }).then(r => r.data),
  getTokenEconomics: (days = 7) => api.get('/analytics/token-economics', { params: { days } }).then(r => r.data),
  getBreakdown: (by = 'client_service_tag', timeRange = '24h', virtualKeyId = null) =>
    api.get('/analytics/breakdown', { params: { by, time_range: timeRange, virtual_key_id: virtualKeyId } }).then(r => r.data),
};
