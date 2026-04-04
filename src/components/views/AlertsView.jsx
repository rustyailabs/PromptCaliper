import React, { useState } from 'react';
import { Plus, Bell, Trash2, BellOff, Clock } from 'lucide-react';
import LoadingSpinner from '../shared/LoadingSpinner';
import ErrorBanner from '../shared/ErrorBanner';
import ConfirmDialog from '../shared/ConfirmDialog';
import FormModal, { Field, Input, Select, FormActions } from '../shared/FormModal';
import { usePolling } from '../../hooks/usePolling';
import { alertService } from '../../services/alertService';

const METRIC_OPTIONS = [
  { value: 'spend_usd', label: 'Spend (USD)', hint: 'Alert when spend exceeds threshold in USD' },
  { value: 'spend_pct', label: 'Spend % of Budget', hint: 'Alert at percentage of monthly budget (e.g. 80)' },
  { value: 'rpm', label: 'Requests per Minute', hint: 'Alert when RPM exceeds threshold' },
  { value: 'error_rate_pct', label: 'Error Rate %', hint: 'Alert when error rate exceeds threshold' },
  { value: 'latency_p95_ms', label: 'P95 Latency (ms)', hint: 'Alert when p95 latency exceeds threshold' },
];

const CHANNEL_OPTIONS = [
  { value: 'log', label: 'Log Only' },
  { value: 'email', label: 'Email' },
  { value: 'webhook', label: 'Webhook (POST)' },
  { value: 'slack', label: 'Slack Webhook' },
];

const SCOPE_BADGE = {
  global: 'bg-[var(--bg-element)] text-[var(--ral-grey-light)]',
  team:  'badge-blue',
  key:   'badge-purple',
  model: 'badge-orange',
};

const METRIC_BADGE = {
  spend_usd:      'badge-orange',
  spend_pct:      'badge-orange',
  rpm:            'badge-cyan',
  error_rate_pct: 'badge-red',
  latency_p95_ms: 'badge-yellow',
};

const DEFAULT_FORM = {
  name: '', metric: 'spend_usd', threshold_value: '',
  scope_type: 'global', scope_id: '',
  notification_channel: 'log', notification_target: '',
};

const AlertsView = () => {
  const { data: rules, isLoading, error, refresh } = usePolling(alertService.listRules, 30000);
  const { data: history } = usePolling(() => alertService.getHistory({ limit: 20 }), 30000);
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
      await alertService.createRule({
        ...form,
        threshold_value: parseFloat(form.threshold_value),
        scope_id: form.scope_id ? parseInt(form.scope_id) : null,
      });
      setShowCreate(false);
      setForm(DEFAULT_FORM);
      refresh();
    } catch (err) {
      setFormError(err?.response?.data?.detail || 'Failed to create alert rule');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await alertService.deleteRule(deleteTarget.id);
      setDeleteTarget(null);
      refresh();
    } catch {}
  }

  if (isLoading) return <div className="flex items-center justify-center py-20"><LoadingSpinner size="lg" /></div>;

  const metricLabel = (m) => METRIC_OPTIONS.find(o => o.value === m)?.label || m;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--ral-white)]">Alerts</h2>
          <p className="text-sm text-[var(--ral-grey-light)]">Threshold-based notifications for spend, rate, and error metrics</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--ral-rust-core)] hover:bg-[var(--ral-rust-bright)] text-white text-sm font-medium transition-colors"
        >
          <Plus size={15} /> Add Rule
        </button>
      </div>

      <ErrorBanner message={error} />

      {/* Alert Rules */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(rules || []).map(r => (
          <div key={r.id} className="glass-panel p-5 rounded-lg border border-[var(--ral-border)]">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <Bell size={15} className="text-[var(--ral-rust-core)]" />
                <h3 className="text-sm font-semibold text-[var(--ral-white)]">{r.name}</h3>
              </div>
              <button onClick={() => setDeleteTarget(r)} className="p-1 text-[var(--ral-grey-mid)] hover:text-red-400">
                <Trash2 size={13} />
              </button>
            </div>

            <div className="flex flex-wrap gap-2 text-xs mb-3">
              <span className={`px-2 py-0.5 rounded font-mono ${METRIC_BADGE[r.metric] || 'bg-[var(--bg-element)] text-[var(--ral-grey-light)]'}`}>
                {metricLabel(r.metric)} &gt; {r.threshold_value}
              </span>
              <span className={`px-2 py-0.5 rounded ${SCOPE_BADGE[r.scope_type] || 'bg-[var(--bg-element)] text-[var(--ral-grey-light)]'}`}>
                {r.scope_type}{r.scope_id ? ` #${r.scope_id}` : ''}
              </span>
              <span className="px-2 py-0.5 rounded bg-[var(--bg-element)] text-[var(--ral-grey-light)]">
                {r.notification_channel}
              </span>
            </div>

            {r.notification_target && (
              <p className="text-[10px] font-mono text-[var(--ral-grey-mid)] truncate">{r.notification_target}</p>
            )}

            {r.last_triggered_at && (
              <p className="text-[10px] text-[var(--ral-grey-mid)] mt-2 flex items-center gap-1">
                <Clock size={10} /> Last fired: {new Date(r.last_triggered_at).toLocaleString()}
              </p>
            )}
          </div>
        ))}
        {(!rules || rules.length === 0) && (
          <div className="col-span-2 glass-panel p-8 rounded-lg text-center">
            <BellOff size={24} className="text-[var(--ral-grey-mid)] mx-auto mb-2" />
            <p className="text-sm text-[var(--ral-grey-mid)]">No alert rules configured. Add one to start monitoring.</p>
          </div>
        )}
      </div>

      {/* Alert History */}
      {history && history.length > 0 && (
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--ral-grey-mid)] mb-3">Recent Alert Events</h3>
          <div className="glass-panel rounded-lg overflow-hidden border border-[var(--ral-border)]">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-element)]">
                  {['Time', 'Rule', 'Metric', 'Value', 'Channel'].map(h => (
                    <th key={h} className="py-2 px-4 text-[10px] font-bold uppercase tracking-wider text-[var(--ral-grey-mid)]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.map(ev => (
                  <tr key={ev.id} className="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-hover)]">
                    <td className="py-2 px-4 font-mono text-xs text-[var(--ral-grey-light)]">
                      {new Date(ev.triggered_at).toLocaleString()}
                    </td>
                    <td className="py-2 px-4 text-xs text-[var(--ral-white)]">{ev.rule_name}</td>
                    <td className="py-2 px-4 text-xs text-[var(--ral-grey-light)]">{metricLabel(ev.metric)}</td>
                    <td className="py-2 px-4 font-mono text-xs text-[var(--ral-rust-bright)]">{ev.actual_value}</td>
                    <td className="py-2 px-4 text-xs text-[var(--ral-grey-mid)]">{ev.channel}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showCreate && (
        <FormModal title="Add Alert Rule" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate}>
            <ErrorBanner message={formError} />
            <Field label="Rule Name">
              <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="High spend warning" required />
            </Field>
            <Field label="Metric">
              <Select value={form.metric} onChange={e => setForm(f => ({ ...f, metric: e.target.value }))}>
                {METRIC_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </Select>
              <p className="text-xs text-[var(--ral-grey-mid)] mt-1">
                {METRIC_OPTIONS.find(o => o.value === form.metric)?.hint}
              </p>
            </Field>
            <Field label="Threshold Value">
              <Input
                type="number"
                step="any"
                value={form.threshold_value}
                onChange={e => setForm(f => ({ ...f, threshold_value: e.target.value }))}
                placeholder={form.metric === 'spend_usd' ? '100.00' : form.metric === 'spend_pct' ? '80' : '60'}
                required
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Scope">
                <Select value={form.scope_type} onChange={e => setForm(f => ({ ...f, scope_type: e.target.value }))}>
                  <option value="global">Global Org</option>
                  <option value="team">Team</option>
                  <option value="key">Virtual Key</option>
                  <option value="model">Model</option>
                </Select>
              </Field>
              {form.scope_type !== 'global' && (
                <Field label="Scope ID">
                  <Input
                    type="number"
                    value={form.scope_id}
                    onChange={e => setForm(f => ({ ...f, scope_id: e.target.value }))}
                    placeholder="e.g. team ID 1"
                  />
                </Field>
              )}
            </div>
            <Field label="Notification Channel">
              <Select value={form.notification_channel} onChange={e => setForm(f => ({ ...f, notification_channel: e.target.value }))}>
                {CHANNEL_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </Select>
            </Field>
            {form.notification_channel !== 'log' && (
              <Field label={form.notification_channel === 'email' ? 'Email Address' : 'Webhook URL'}>
                <Input
                  value={form.notification_target}
                  onChange={e => setForm(f => ({ ...f, notification_target: e.target.value }))}
                  placeholder={form.notification_channel === 'email' ? 'ops@company.com' : 'https://hooks.slack.com/...'}
                  required
                />
              </Field>
            )}
            <FormActions onCancel={() => setShowCreate(false)} submitLabel="Add Rule" loading={saving} />
          </form>
        </FormModal>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Delete Alert Rule"
          message={`Delete rule "${deleteTarget.name}"?`}
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
};

export default AlertsView;
