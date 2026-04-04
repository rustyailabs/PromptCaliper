import { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import {
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';
import LoadingSpinner from '../shared/LoadingSpinner';
import ErrorBanner from '../shared/ErrorBanner';
import ConfirmDialog from '../shared/ConfirmDialog';
import FormModal, { Field, Input, Select, FormActions } from '../shared/FormModal';
import { usePolling } from '../../hooks/usePolling';
import { budgetService } from '../../services/budgetService';

const COLORS = ['var(--ral-rust-core)', 'var(--ral-cyan)', 'var(--ral-rust-bright)', 'var(--ral-grey-light)', '#a78bfa'];

const DEFAULT_FORM = { name: '', scope_type: 'global', scope_id: '', monthly_limit_usd: '', action_on_breach: 'block' };

function SpendCard({ label, value, budget, color }) {
  const pct = budget ? Math.min(100, (value / budget) * 100) : null;
  return (
    <div className="glass-panel p-5 rounded-lg" style={{ borderLeftWidth: 4, borderLeftColor: color, borderLeftStyle: 'solid' }}>
      <p className="text-xs text-[var(--ral-grey-mid)] uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-[var(--ral-white)]">${parseFloat(value || 0).toFixed(4)}</p>
      {budget && (
        <div className="mt-3">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-[var(--ral-grey-mid)]">vs ${parseFloat(budget).toFixed(2)} budget</span>
            <span className={`font-mono ${pct >= 90 ? 'text-[var(--ral-rust-bright)]' : 'text-[var(--ral-cyan)]'}`}>{pct?.toFixed(1)}%</span>
          </div>
          <div className="w-full h-1.5 bg-[var(--bg-element)] rounded-full overflow-hidden">
            <div className="h-full transition-all" style={{ width: `${pct}%`, backgroundColor: pct >= 90 ? 'var(--ral-rust-bright)' : color }} />
          </div>
        </div>
      )}
    </div>
  );
}

const BudgetSpendView = ({ timeRange = '24h' }) => {
  const { data: summary } = usePolling(() => budgetService.getSummary(), 30000);
  const { data: byTeam, isLoading: loadingTeam } = usePolling(() => budgetService.getSpendByTeam(), 30000);
  const { data: byModel, isLoading: loadingModel } = usePolling(() => budgetService.getSpendByModel(), 30000);
  const { data: byKey } = usePolling(() => budgetService.getSpendByKey(), 30000);
  const { data: policies, refresh: refreshPolicies } = usePolling(budgetService.listPolicies, 30000);
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
      await budgetService.createPolicy({
        ...form,
        scope_id: form.scope_id ? parseInt(form.scope_id) : null,
        monthly_limit_usd: parseFloat(form.monthly_limit_usd),
      });
      setShowCreate(false);
      setForm(DEFAULT_FORM);
      refreshPolicies();
    } catch (err) {
      setFormError(err?.response?.data?.detail || 'Failed to create policy');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await budgetService.deletePolicy(deleteTarget.id);
      setDeleteTarget(null);
      refreshPolicies();
    } catch {}
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <SpendCard label="Org Spend (current month)" value={summary?.total_spend_usd} budget={null} color="var(--ral-rust-core)" />
        <div className="glass-panel p-5 rounded-lg" style={{ borderLeftWidth: 4, borderLeftColor: 'var(--ral-cyan)', borderLeftStyle: 'solid' }}>
          <p className="text-xs text-[var(--ral-grey-mid)] uppercase tracking-wider mb-1">Total Prompt Tokens</p>
          <p className="text-2xl font-bold text-[var(--ral-white)]">{(summary?.prompt_tokens || 0).toLocaleString()}</p>
        </div>
        <div className="glass-panel p-5 rounded-lg" style={{ borderLeftWidth: 4, borderLeftColor: 'var(--ral-rust-bright)', borderLeftStyle: 'solid' }}>
          <p className="text-xs text-[var(--ral-grey-mid)] uppercase tracking-wider mb-1">Total Completion Tokens</p>
          <p className="text-2xl font-bold text-[var(--ral-white)]">{(summary?.completion_tokens || 0).toLocaleString()}</p>
        </div>
      </div>

      {/* Spend by Team + Model */}
      <div className="grid grid-cols-2 gap-6">
        <div className="glass-panel p-6 rounded-lg">
          <h3 className="text-[var(--ral-white)] font-semibold mb-4">Spend by Team (this month)</h3>
          {loadingTeam ? <div className="h-48 flex items-center justify-center"><LoadingSpinner /></div> : (
            <div className="space-y-3">
              {(byTeam || []).map((t, i) => (
                <div key={t.team_id} className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                  <span className="text-xs text-[var(--ral-grey-light)] flex-1 truncate">{t.team_name}</span>
                  <div className="flex-1 h-1.5 bg-[var(--bg-element)] rounded-full overflow-hidden">
                    <div className="h-full" style={{ width: `${t.spend_pct || 0}%`, backgroundColor: COLORS[i % COLORS.length] }} />
                  </div>
                  <span className="text-xs font-mono text-[var(--ral-rust-bright)] w-20 text-right">${parseFloat(t.spend_usd || 0).toFixed(4)}</span>
                  {t.budget_usd && <span className="text-xs text-[var(--ral-grey-mid)]">/ ${parseFloat(t.budget_usd).toFixed(2)}</span>}
                </div>
              ))}
              {(!byTeam || byTeam.length === 0) && <p className="text-xs text-[var(--ral-grey-mid)]">No team spend data yet.</p>}
            </div>
          )}
        </div>

        <div className="glass-panel p-6 rounded-lg">
          <h3 className="text-[var(--ral-white)] font-semibold mb-4">Token Usage by Model (this month)</h3>
          {loadingModel ? <div className="h-40 flex items-center justify-center"><LoadingSpinner /></div>
            : (!byModel || byModel.length === 0) ? (
              <p className="text-xs text-[var(--ral-grey-mid)] mt-4">No model usage this month.</p>
            ) : (
            <div className="flex flex-col gap-3">
              {/* Pie — no inline labels, properly centred */}
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={byModel}
                      dataKey="total_tokens"
                      nameKey="model_name"
                      cx="50%" cy="50%"
                      outerRadius={60}
                      innerRadius={28}
                      label={false}
                      paddingAngle={2}
                    >
                      {byModel.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: 'var(--ral-grey-dark)', borderColor: 'var(--ral-rust-core)', borderRadius: 6, padding: '6px 10px' }}
                      labelStyle={{ color: 'var(--ral-grey-mid)', fontSize: 11 }}
                      itemStyle={{ color: 'var(--ral-white)', fontSize: 11 }}
                      formatter={(v, _name, props) => [`${parseInt(v).toLocaleString()} tokens`, props.payload.model_name]}
                      separator=": "
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              {/* Legend list */}
              <div className="space-y-1.5">
                {byModel.slice(0, 5).map((m, i) => {
                  const total = byModel.reduce((s, x) => s + x.total_tokens, 0);
                  const pct = total > 0 ? ((m.total_tokens / total) * 100).toFixed(0) : 0;
                  return (
                    <div key={m.model_name} className="flex items-center gap-2 text-xs">
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                      <span className="flex-1 truncate text-[var(--ral-grey-light)]">{m.model_name?.split('/').pop()}</span>
                      <span className="font-mono text-[var(--ral-grey-mid)]">{parseInt(m.total_tokens).toLocaleString()}tk</span>
                      <span className="font-mono text-[var(--ral-white)] w-8 text-right">{pct}%</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Key spend table */}
      {byKey && byKey.length > 0 && (
        <div className="glass-panel rounded-lg overflow-hidden border border-[var(--ral-border)]">
          <div className="p-4 border-b border-[var(--border-subtle)] bg-[var(--bg-element)]">
            <h3 className="font-semibold text-[var(--ral-white)] text-sm">Spend by Virtual Key (current month)</h3>
          </div>
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-element)]">
                {['Key', 'Owner', 'Spend', 'Budget', 'Usage'].map(h => (
                  <th key={h} className="py-2 px-4 text-[10px] font-bold uppercase tracking-wider text-[var(--ral-grey-mid)]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {byKey.map(k => {
                const pct = k.spend_pct || 0;
                return (
                  <tr key={k.key_id} className="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-hover)]">
                    <td className="py-2 px-4 font-mono text-xs text-[var(--ral-white)]">{k.key_prefix}</td>
                    <td className="py-2 px-4 text-xs text-[var(--ral-grey-light)]">{k.owner_label}</td>
                    <td className="py-2 px-4 font-mono text-xs text-[var(--ral-rust-bright)]">${parseFloat(k.spend_usd || 0).toFixed(4)}</td>
                    <td className="py-2 px-4 font-mono text-xs text-[var(--ral-grey-light)]">{k.budget_usd ? `$${parseFloat(k.budget_usd).toFixed(2)}` : '—'}</td>
                    <td className="py-2 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-20 h-1.5 bg-[var(--bg-element)] rounded-full overflow-hidden">
                          <div className={`h-full ${pct >= 90 ? 'bg-[var(--ral-rust-bright)]' : 'bg-[var(--ral-cyan)]'}`} style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-xs font-mono text-[var(--ral-grey-mid)]">{pct?.toFixed(0)}%</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Budget Policies */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[var(--ral-grey-light)] uppercase tracking-widest text-xs font-bold">Budget Policies</h3>
          <button onClick={() => setShowCreate(true)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--ral-rust-core)] hover:bg-[var(--ral-rust-bright)] text-white text-xs font-medium transition-colors">
            <Plus size={14} /> Add Policy
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(policies || []).map(p => (
            <div key={p.id} className="glass-panel p-4 rounded-lg">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <p className="text-sm font-semibold text-[var(--ral-white)]">{p.name}</p>
                  <p className="text-xs text-[var(--ral-grey-mid)] uppercase tracking-wider">{p.scope_type}</p>
                </div>
                <button onClick={() => setDeleteTarget(p)} className="text-[var(--ral-grey-mid)] hover:text-red-400"><Trash2 size={14} /></button>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[var(--ral-grey-light)]">Limit: <span className="font-mono text-[var(--ral-white)]">${parseFloat(p.monthly_limit_usd).toFixed(2)}/mo</span></span>
                <span className={`font-mono px-2 py-0.5 rounded text-xs ${p.action_on_breach === 'block' ? 'badge-red' : p.action_on_breach === 'alert' ? 'badge-yellow' : 'badge-orange'}`}>
                  {p.action_on_breach}
                </span>
              </div>
            </div>
          ))}
          {(!policies || policies.length === 0) && (
            <div className="col-span-3 glass-panel p-6 rounded-lg text-center text-sm text-[var(--ral-grey-mid)]">
              No budget policies. Add one to set spending limits.
            </div>
          )}
        </div>
      </div>

      {showCreate && (
        <FormModal title="Create Budget Policy" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate}>
            <ErrorBanner message={formError} />
            <Field label="Policy Name"><Input value={form.name} onChange={e => setForm(f => ({...f, name: e.target.value}))} placeholder="Engineering Team Monthly" required /></Field>
            <Field label="Scope">
              <Select value={form.scope_type} onChange={e => setForm(f => ({...f, scope_type: e.target.value}))}>
                <option value="global">Global Org</option>
                <option value="team">Team</option>
                <option value="key">Virtual Key</option>
                <option value="model">Model</option>
              </Select>
            </Field>
            {form.scope_type !== 'global' && (
              <Field label="Scope ID"><Input type="number" value={form.scope_id} onChange={e => setForm(f => ({...f, scope_id: e.target.value}))} placeholder="e.g. team ID 1" /></Field>
            )}
            <Field label="Monthly Limit (USD)"><Input type="number" step="0.01" value={form.monthly_limit_usd} onChange={e => setForm(f => ({...f, monthly_limit_usd: e.target.value}))} placeholder="500.00" required /></Field>
            <Field label="On Breach">
              <Select value={form.action_on_breach} onChange={e => setForm(f => ({...f, action_on_breach: e.target.value}))}>
                <option value="block">Block (429)</option>
                <option value="alert">Alert Only</option>
                <option value="both">Block + Alert</option>
              </Select>
            </Field>
            <FormActions onCancel={() => setShowCreate(false)} submitLabel="Create Policy" loading={saving} />
          </form>
        </FormModal>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Delete Budget Policy"
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

export default BudgetSpendView;
