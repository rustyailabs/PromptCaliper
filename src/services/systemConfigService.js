/**
 * systemConfigService.js
 *
 * Frontend service for the superadmin runtime-settings API.
 *
 * Endpoints (both require superadmin JWT):
 *   GET  /api/users/runtime-settings  → { log_prompt_content: bool }
 *   PATCH /api/users/runtime-settings ← { log_prompt_content: bool }
 *
 * These are deliberately scoped under /users rather than a separate route
 * because the users.py router is already superadmin-gated, avoiding the
 * need for a new router file or additional auth wiring on the backend.
 */

import api from './api';

export const systemConfigService = {
  /** Fetch the current runtime configuration flags. */
  get: () => api.get('/users/runtime-settings').then(r => r.data),

  /** Update one or more runtime configuration flags.
   *  @param {Object} body - e.g. { log_prompt_content: true }
   */
  update: (body) => api.patch('/users/runtime-settings', body).then(r => r.data),
};
