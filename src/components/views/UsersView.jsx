import React, { useState, useEffect, useContext } from 'react';
import { Search, Users, Key, Plus, Trash2, Settings } from 'lucide-react';
import Badge from '../shared/Badge';
import LoadingSpinner from '../shared/LoadingSpinner';
import ErrorBanner from '../shared/ErrorBanner';
import ConfirmDialog from '../shared/ConfirmDialog';
import FormModal, { Field, Input, Select, FormActions } from '../shared/FormModal';
import { usePolling } from '../../hooks/usePolling';
import { userService } from '../../services/userService';
import { systemConfigService } from '../../services/systemConfigService';
import { AuthContext } from '../../context/AuthContext';

const DEFAULT_FORM = { username: '', email: '', password: '', is_superadmin: false };

const UsersView = () => {
  const { user: currentUser } = useContext(AuthContext);
  const { data: users, isLoading, error, refresh } = usePolling(userService.list, 30000);
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  // ── Runtime system settings (superadmin only) ───────────────────────────
  // Loaded once on mount; the toggle calls PATCH immediately on change.
  // Only rendered when currentUser.is_superadmin is true — the backend also
  // enforces this at the API level (HTTP 403 for non-superadmins).
  const [logPromptContent, setLogPromptContent] = useState(false);
  const [configLoading, setConfigLoading] = useState(false);
  const [configError, setConfigError] = useState('');

  useEffect(() => {
    if (!currentUser?.is_superadmin) return;
    systemConfigService.get()
      .then(data => setLogPromptContent(data.log_prompt_content))
      .catch(() => setConfigError('Failed to load system settings'));
  }, [currentUser]);

  async function handleToggleLogPromptContent(value) {
    setConfigLoading(true);
    setConfigError('');
    try {
      const updated = await systemConfigService.update({ log_prompt_content: value });
      setLogPromptContent(updated.log_prompt_content);
    } catch {
      setConfigError('Failed to update setting');
    } finally {
      setConfigLoading(false);
    }
  }

  const filtered = (users || []).filter(u =>
    u.username.toLowerCase().includes(search.toLowerCase()) ||
    u.email.toLowerCase().includes(search.toLowerCase())
  );

  async function handleCreate(e) {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      await userService.create(form);
      setShowCreate(false);
      setForm(DEFAULT_FORM);
      refresh();
    } catch (err) {
      setFormError(err?.response?.data?.detail || 'Failed to create user');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await userService.delete(deleteTarget.id);
      setDeleteTarget(null);
      refresh();
    } catch {}
  }

  if (isLoading) return <div className="flex items-center justify-center py-20"><LoadingSpinner size="lg" /></div>;

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} />
      <div className="flex justify-between items-center mb-4">
        <div className="relative w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ral-grey-mid)]" size={14} />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Find user..."
            className="w-full bg-[var(--bg-element)] border border-[var(--border-element)] rounded-md pl-9 pr-3 py-1.5 text-sm text-[var(--ral-white)] focus:border-[var(--ral-rust-core)] focus:outline-none"
          />
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--ral-rust-core)] text-white rounded hover:bg-[var(--ral-rust-bright)] transition-colors"
        >
          <Plus size={16} /> Invite User
        </button>
      </div>

      {/* System Settings — visible to superadmins only.
          The toggle controls LOG_PROMPT_CONTENT at runtime: when enabled,
          full prompt messages and LLM responses are stored in request_logs.
          Keep disabled in production unless actively debugging — enabling
          this stores potentially sensitive user content in the database. */}
      {currentUser?.is_superadmin && (
        <div className="glass-panel rounded-lg border border-[var(--ral-border)] p-5 mb-2">
          <div className="flex items-center gap-2 mb-4">
            <Settings size={15} className="text-[var(--ral-rust-core)]" />
            <h3 className="text-sm font-semibold text-[var(--ral-white)]">System Settings</h3>
          </div>
          <ErrorBanner message={configError} />
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-sm font-medium text-[var(--ral-white)]">Log Prompt Content</p>
              <p className="text-xs text-[var(--ral-grey-mid)] mt-0.5">
                Store full prompt messages and LLM responses in request logs.
                Disable in production unless debugging.
              </p>
            </div>
            <button
              role="switch"
              aria-checked={logPromptContent}
              disabled={configLoading}
              onClick={() => handleToggleLogPromptContent(!logPromptContent)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none
                ${logPromptContent ? 'bg-[var(--ral-rust-core)]' : 'bg-[var(--ral-grey-dark)]'}
                ${configLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform
                  ${logPromptContent ? 'translate-x-6' : 'translate-x-1'}`}
              />
            </button>
          </div>
        </div>
      )}

      <div className="glass-panel rounded-lg overflow-hidden border border-[var(--ral-border)]">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-element)]">
              {['User', 'Email', 'Role', 'Status', 'Last Login', 'Actions'].map(h => (
                <th key={h} className="py-3 px-6 text-[10px] font-bold uppercase tracking-wider text-[var(--ral-grey-mid)]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={6} className="py-8 text-center text-xs text-[var(--ral-grey-mid)]">No users found</td></tr>
            ) : (
              filtered.map((user) => (
                <tr key={user.id} className="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-hover)]">
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[var(--ral-grey-mid)] flex items-center justify-center text-xs font-bold text-white">
                        {user.username.charAt(0).toUpperCase()}
                      </div>
                      <span className="font-medium text-sm text-[var(--ral-white)]">{user.username}</span>
                    </div>
                  </td>
                  <td className="py-4 px-6 text-sm text-[var(--ral-grey-light)]">{user.email}</td>
                  <td className="py-4 px-6 text-sm text-[var(--ral-grey-light)]">{user.is_superadmin ? 'Superadmin' : 'Admin'}</td>
                  <td className="py-4 px-6"><Badge status={user.is_active ? '200' : 'maintenance'} /></td>
                  <td className="py-4 px-6 font-mono text-xs text-[var(--ral-grey-light)]">
                    {user.last_login_at ? new Date(user.last_login_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="py-4 px-6 text-right">
                    <button
                      onClick={() => setDeleteTarget(user)}
                      className="p-1.5 text-[var(--ral-grey-mid)] hover:text-red-400 transition-colors"
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <FormModal title="Invite Admin User" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate}>
            <ErrorBanner message={formError} />
            <Field label="Username"><Input value={form.username} onChange={e => setForm(f => ({...f, username: e.target.value}))} placeholder="alice.chen" required /></Field>
            <Field label="Email"><Input type="email" value={form.email} onChange={e => setForm(f => ({...f, email: e.target.value}))} placeholder="alice@example.com" required /></Field>
            <Field label="Password"><Input type="password" value={form.password} onChange={e => setForm(f => ({...f, password: e.target.value}))} placeholder="Temporary password" required /></Field>
            <Field label="Role">
              <Select value={form.is_superadmin ? 'super' : 'admin'} onChange={e => setForm(f => ({...f, is_superadmin: e.target.value === 'super'}))}>
                <option value="admin">Admin</option>
                <option value="super">Superadmin</option>
              </Select>
            </Field>
            <FormActions onCancel={() => setShowCreate(false)} submitLabel="Create User" loading={saving} />
          </form>
        </FormModal>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Delete User"
          message={`Delete admin user "${deleteTarget.username}"? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
};

export default UsersView;
