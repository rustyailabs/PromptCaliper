import React, { useState } from 'react';
import { Plus, Key, Trash2, RefreshCw, Copy, Check, Eye, EyeOff } from 'lucide-react';
import Badge from '../shared/Badge';
import LoadingSpinner from '../shared/LoadingSpinner';
import ErrorBanner from '../shared/ErrorBanner';
import ConfirmDialog from '../shared/ConfirmDialog';
import FormModal, { Field, Input, Select, FormActions } from '../shared/FormModal';
import { usePolling } from '../../hooks/usePolling';
import { virtualKeyService } from '../../services/virtualKeyService';
import { teamService } from '../../services/teamService';

const DEFAULT_FORM = {
  owner_label: '', team_id: '', monthly_budget_usd: '',
  budget_action: 'block', rpm_limit: '', tpm_limit: '',
};

function SpendBar({ spend, budget }) {
  if (!budget) return <span className="text-xs text-[var(--ral-grey-mid)]">No limit</span>;
  const pct = Math.min(100, (spend / budget) * 100);
  const color = pct >= 90 ? 'bg-[var(--ral-rust-bright)]' : pct >= 70 ? 'bg-yellow-500' : 'bg-[var(--ral-cyan)]';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-[var(--bg-element)] rounded-full overflow-hidden min-w-[60px]">
        <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-[var(--ral-grey-light)] whitespace-nowrap">
        ${parseFloat(spend || 0).toFixed(3)} / ${parseFloat(budget).toFixed(2)}
      </span>
    </div>
  );
}

function CopyButton({ value }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      className="p-1 text-[var(--ral-grey-mid)] hover:text-[var(--ral-white)]"
    >
      {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
    </button>
  );
}

const VirtualKeysView = () => {
  const { data: keys, isLoading, error, refresh } = usePolling(virtualKeyService.list, 30000);
  const { data: teams } = usePolling(teamService.list, 60000);
  const [showCreate, setShowCreate] = useState(false);
  const [createdKey, setCreatedKey] = useState(null); // one-time reveal
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  async function handleCreate(e) {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      const result = await virtualKeyService.create({
        owner_label: form.owner_label,
        team_id: form.team_id ? parseInt(form.team_id) : null,
        monthly_budget_usd: form.monthly_budget_usd ? parseFloat(form.monthly_budget_usd) : null,
        budget_action: form.budget_action,
        rpm_limit: form.rpm_limit ? parseInt(form.rpm_limit) : null,
        tpm_limit: form.tpm_limit ? parseInt(form.tpm_limit) : null,
      });
      setShowCreate(false);
      setForm(DEFAULT_FORM);
      setCreatedKey(result); // show one-time reveal modal
      refresh();
    } catch (err) {
      setFormError(err?.response?.data?.detail || 'Failed to create key');
    } finally {
      setSaving(false);
    }
  }

  async function handleRotate(key) {
    try {
      const result = await virtualKeyService.rotate(key.id);
      setCreatedKey(result);
      refresh();
    } catch {}
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await virtualKeyService.delete(deleteTarget.id);
      setDeleteTarget(null);
      refresh();
    } catch {}
  }

  if (isLoading) return <div className="flex items-center justify-center py-20"><LoadingSpinner size="lg" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--ral-white)]">Virtual Keys</h2>
          <p className="text-sm text-[var(--ral-grey-light)]">{keys?.length ?? 0} keys · budget & rate limits per key</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--ral-rust-core)] hover:bg-[var(--ral-rust-bright)] text-white text-sm font-medium transition-colors"
        >
          <Plus size={15} /> New Key
        </button>
      </div>

      <ErrorBanner message={error} />

      <div className="glass-panel rounded-lg overflow-hidden border border-[var(--ral-border)]">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-element)]">
              {['Key', 'Owner', 'Team', 'Spend vs Budget', 'RPM', 'Expires', 'Status', 'Actions'].map(h => (
                <th key={h} className="py-3 px-4 text-[10px] font-bold uppercase tracking-wider text-[var(--ral-grey-mid)]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(!keys || keys.length === 0) ? (
              <tr><td colSpan={8} className="py-8 text-center text-xs text-[var(--ral-grey-mid)]">No virtual keys yet. Create one to get started.</td></tr>
            ) : (
              (keys || []).map((key) => (
                <tr key={key.id} className="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-hover)]">
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2 font-mono text-xs bg-[var(--bg-element)] px-2 py-1 rounded w-fit border border-[var(--border-element)]">
                      <Key size={10} className="text-[var(--ral-rust-core)]" />
                      <span className="text-[var(--ral-white)]">{key.key_prefix}</span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-sm text-[var(--ral-white)]">{key.owner_label}</td>
                  <td className="py-3 px-4 text-xs text-[var(--ral-grey-light)]">{key.team_name || '—'}</td>
                  <td className="py-3 px-4 min-w-[160px]">
                    <SpendBar spend={key.current_spend_usd} budget={key.monthly_budget_usd} />
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-[var(--ral-grey-light)]">{key.rpm_limit ?? '—'}</td>
                  <td className="py-3 px-4 font-mono text-xs text-[var(--ral-grey-light)]">
                    {key.expires_at ? new Date(key.expires_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="py-3 px-4"><Badge status={key.is_active ? '200' : 'maintenance'} /></td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-1">
                      <button onClick={() => handleRotate(key)} title="Rotate key" className="p-1.5 text-[var(--ral-grey-mid)] hover:text-[var(--ral-cyan)]"><RefreshCw size={14} /></button>
                      <button onClick={() => setDeleteTarget(key)} title="Delete" className="p-1.5 text-[var(--ral-grey-mid)] hover:text-red-400"><Trash2 size={14} /></button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create modal */}
      {showCreate && (
        <FormModal title="Create Virtual Key" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate}>
            <ErrorBanner message={formError} />
            <Field label="Owner / Service Label"><Input value={form.owner_label} onChange={e => setForm(f => ({...f, owner_label: e.target.value}))} placeholder="alice.chen or svc-analytics-bot" required /></Field>
            <Field label="Team">
              <Select value={form.team_id} onChange={e => setForm(f => ({...f, team_id: e.target.value}))}>
                <option value="">No team</option>
                {(teams || []).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Monthly Budget (USD)"><Input type="number" step="0.01" value={form.monthly_budget_usd} onChange={e => setForm(f => ({...f, monthly_budget_usd: e.target.value}))} placeholder="50.00" /></Field>
              <Field label="On Budget Breach">
                <Select value={form.budget_action} onChange={e => setForm(f => ({...f, budget_action: e.target.value}))}>
                  <option value="block">Block (429)</option>
                  <option value="alert">Alert Only</option>
                  <option value="both">Block + Alert</option>
                </Select>
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="RPM Limit"><Input type="number" value={form.rpm_limit} onChange={e => setForm(f => ({...f, rpm_limit: e.target.value}))} placeholder="60" /></Field>
              <Field label="TPM Limit"><Input type="number" value={form.tpm_limit} onChange={e => setForm(f => ({...f, tpm_limit: e.target.value}))} placeholder="100000" /></Field>
            </div>
            <FormActions onCancel={() => setShowCreate(false)} submitLabel="Create Key" loading={saving} />
          </form>
        </FormModal>
      )}

      {/* One-time key reveal */}
      {createdKey && (
        <FormModal title="Key Created — Save This Now" onClose={() => setCreatedKey(null)}>
          <p className="text-sm text-[var(--ral-grey-light)] mb-4">This is the only time the full key will be shown. Copy it now.</p>
          <div className="flex items-center gap-2 font-mono text-sm bg-[var(--ral-black)] border border-[var(--ral-rust-core)] rounded-lg px-4 py-3 text-[var(--ral-rust-bright)]">
            <span className="flex-1 break-all">{createdKey.full_key}</span>
            <CopyButton value={createdKey.full_key} />
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-[var(--ral-grey-mid)]">
            <div>Owner: <span className="text-[var(--ral-white)]">{createdKey.owner_label}</span></div>
            <div>Budget: <span className="text-[var(--ral-white)]">{createdKey.monthly_budget_usd ? `$${createdKey.monthly_budget_usd}/mo` : 'Unlimited'}</span></div>
          </div>
          <div className="mt-6 flex justify-end">
            <button onClick={() => setCreatedKey(null)} className="px-4 py-2 rounded-lg bg-[var(--ral-rust-core)] hover:bg-[var(--ral-rust-bright)] text-white text-sm font-medium">
              I've saved it
            </button>
          </div>
        </FormModal>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Delete Virtual Key"
          message={`Delete key "${deleteTarget.key_prefix}" for ${deleteTarget.owner_label}? All requests using this key will be rejected.`}
          confirmLabel="Delete Key"
          danger
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
};

export default VirtualKeysView;
