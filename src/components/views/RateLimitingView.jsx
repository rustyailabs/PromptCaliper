import React, { useState } from 'react';
import { Plus, DollarSign, Clock, ShieldAlert, Trash2 } from 'lucide-react';
import Badge from '../shared/Badge';
import LoadingSpinner from '../shared/LoadingSpinner';
import ErrorBanner from '../shared/ErrorBanner';
import ConfirmDialog from '../shared/ConfirmDialog';
import FormModal, { Field, Input, Select, FormActions } from '../shared/FormModal';
import { usePolling } from '../../hooks/usePolling';
import { rateLimitService } from '../../services/rateLimitService';

const DEFAULT_FORM = { name: '', scope_type: 'global', scope_id: '', rpm_limit: '', tpm_limit: '' };

const RateLimitingView = () => {
  const { data: policies, isLoading, error, refresh } = usePolling(rateLimitService.listPolicies, 30000);
  const { data: usage } = usePolling(rateLimitService.getCurrentUsage, 30000);
  const [showCreate, setShowCreate] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  async function handleCreate(e) {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      await rateLimitService.createPolicy({
        ...form,
        scope_id: form.scope_id ? parseInt(form.scope_id) : null,
        rpm_limit: form.rpm_limit ? parseInt(form.rpm_limit) : null,
        tpm_limit: form.tpm_limit ? parseInt(form.tpm_limit) : null,
      });
      setShowCreate(false);
      setForm(DEFAULT_FORM);
      refresh();
    } catch (err) {
      setFormError(err?.response?.data?.detail || 'Failed to create policy');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await rateLimitService.deletePolicy(deleteTarget.id);
      setDeleteTarget(null);
      refresh();
    } catch {}
  }

  if (isLoading) return <div className="flex items-center justify-center py-20"><LoadingSpinner size="lg" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-[var(--ral-white)]">Policy Management</h2>
          <p className="text-sm text-[var(--ral-grey-light)]">Control usage quotas and rate limits</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--ral-rust-core)] text-white rounded hover:bg-[var(--ral-rust-bright)] transition-colors shadow-[0_0_15px_rgba(192,83,26,0.3)]"
        >
          <Plus size={16} /> Create Policy
        </button>
      </div>

      <ErrorBanner message={error} />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {(policies || []).map((policy) => (
          <div key={policy.id} className="glass-panel rounded-lg p-6 flex flex-col justify-between group transition-all">
            <div>
              <div className="flex justify-between items-start mb-4">
                <div className={`p-2 rounded bg-[rgba(255,255,255,0.05)] ${policy.is_active ? 'text-[var(--ral-cyan)]' : 'text-[var(--ral-grey-mid)]'}`}>
                  <ShieldAlert size={20} />
                </div>
                <button onClick={() => setDeleteTarget(policy)} className="text-[var(--ral-grey-mid)] hover:text-red-400 transition-colors">
                  <Trash2 size={15} />
                </button>
              </div>
              <h3 className="text-lg font-bold text-[var(--ral-white)] mb-1">{policy.name}</h3>
              <p className="text-xs text-[var(--ral-grey-light)] uppercase tracking-wider mb-4">{policy.scope_type}</p>
              <div className="space-y-2">
                {policy.rpm_limit && (
                  <div className="flex justify-between text-xs">
                    <span className="text-[var(--ral-grey-mid)]">RPM Limit</span>
                    <span className="font-mono text-[var(--ral-white)]">{policy.rpm_limit.toLocaleString()}</span>
                  </div>
                )}
                {policy.tpm_limit && (
                  <div className="flex justify-between text-xs">
                    <span className="text-[var(--ral-grey-mid)]">TPM Limit</span>
                    <span className="font-mono text-[var(--ral-white)]">{policy.tpm_limit.toLocaleString()}</span>
                  </div>
                )}
              </div>
            </div>
            <div className="mt-4 flex justify-between items-center">
              <Badge status={policy.is_active ? '200' : 'maintenance'} />
              <span className="text-xs text-[var(--ral-grey-mid)]">{new Date(policy.created_at).toLocaleDateString()}</span>
            </div>
          </div>
        ))}
        {(!policies || policies.length === 0) && (
          <div className="col-span-3 glass-panel p-8 rounded-lg text-center text-sm text-[var(--ral-grey-mid)]">
            No rate limiting policies configured.
          </div>
        )}
      </div>

      {/* Live usage table */}
      {usage && usage.length > 0 && (
        <div className="glass-panel rounded-lg overflow-hidden border border-[var(--ral-border)]">
          <div className="p-4 border-b border-[var(--border-subtle)] bg-[var(--bg-element)]">
            <h3 className="font-semibold text-[var(--ral-white)] text-sm">Live Key Usage (current minute)</h3>
          </div>
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-element)]">
                {['Key', 'RPM Used', 'RPM Limit', 'TPM Used', 'TPM Limit'].map(h => (
                  <th key={h} className="py-2 px-4 text-[10px] font-bold uppercase tracking-wider text-[var(--ral-grey-mid)]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {usage.map(u => (
                <tr key={u.key_id} className="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-hover)]">
                  <td className="py-2 px-4 font-mono text-xs text-[var(--ral-white)]">{u.key_prefix}</td>
                  <td className={`py-2 px-4 font-mono text-xs ${u.rpm >= u.rpm_limit ? 'text-[var(--ral-rust-bright)]' : 'text-[var(--ral-cyan)]'}`}>{u.rpm}</td>
                  <td className="py-2 px-4 font-mono text-xs text-[var(--ral-grey-light)]">{u.rpm_limit}</td>
                  <td className="py-2 px-4 font-mono text-xs text-[var(--ral-white)]">{u.tpm}</td>
                  <td className="py-2 px-4 font-mono text-xs text-[var(--ral-grey-light)]">{u.tpm_limit ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <FormModal title="Create Rate Limit Policy" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate}>
            <ErrorBanner message={formError} />
            <Field label="Policy Name"><Input value={form.name} onChange={e => setForm(f => ({...f, name: e.target.value}))} placeholder="Team Engineering Limit" required /></Field>
            <Field label="Scope">
              <Select value={form.scope_type} onChange={e => setForm(f => ({...f, scope_type: e.target.value}))}>
                <option value="global">Global</option>
                <option value="team">Team</option>
                <option value="key">Virtual Key</option>
              </Select>
            </Field>
            {form.scope_type !== 'global' && (
              <Field label="Scope ID (team or key ID)"><Input type="number" value={form.scope_id} onChange={e => setForm(f => ({...f, scope_id: e.target.value}))} placeholder="1" /></Field>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Field label="RPM Limit" hint="Requests per minute"><Input type="number" value={form.rpm_limit} onChange={e => setForm(f => ({...f, rpm_limit: e.target.value}))} placeholder="60" /></Field>
              <Field label="TPM Limit" hint="Tokens per minute"><Input type="number" value={form.tpm_limit} onChange={e => setForm(f => ({...f, tpm_limit: e.target.value}))} placeholder="100000" /></Field>
            </div>
            <FormActions onCancel={() => setShowCreate(false)} submitLabel="Create Policy" loading={saving} />
          </form>
        </FormModal>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Delete Policy"
          message={`Delete policy "${deleteTarget.name}"?`}
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
};

export default RateLimitingView;
