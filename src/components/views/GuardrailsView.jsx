import { useState } from 'react';
import { Plus, Shield, Trash2, TestTube, CheckCircle, XCircle } from 'lucide-react';
import LoadingSpinner from '../shared/LoadingSpinner';
import ErrorBanner from '../shared/ErrorBanner';
import ConfirmDialog from '../shared/ConfirmDialog';
import FormModal, { Field, Input, Select, FormActions } from '../shared/FormModal';
import { usePolling } from '../../hooks/usePolling';
import { guardrailService } from '../../services/guardrailService';

const GUARDRAIL_TYPES = [
  { value: 'keyword_block', label: 'Keyword Block', hint: 'JSON: {"keywords": ["word1", "word2"]}' },
  { value: 'regex_filter', label: 'Regex Filter', hint: 'JSON: {"pattern": "\\\\bsensitive\\\\b"}' },
  { value: 'pii_redaction', label: 'PII Redaction', hint: 'Redacts emails, SSNs, phone numbers, credit cards. Config: {}' },
  { value: 'content_filter', label: 'Content Filter', hint: 'JSON: {"categories": ["violence", "adult"]}' },
];

const DEFAULT_FORM = {
  name: '', guardrail_type: 'keyword_block', applies_to: 'both',
  config_json: '{}', action_on_trigger: 'block',
};

const TYPE_BADGE_COLORS = {
  keyword_block: 'badge-orange',
  regex_filter:  'badge-purple',
  pii_redaction: 'badge-blue',
  content_filter:'badge-red',
};

const GuardrailsView = () => {
  const { data: guardrails, isLoading, error, refresh } = usePolling(guardrailService.list, 30000);
  const [showCreate, setShowCreate] = useState(false);
  const [showTest, setShowTest] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');
  const [testInput, setTestInput] = useState('');
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      let configJson = {};
      try { configJson = JSON.parse(form.config_json); } catch { setFormError('Config JSON is invalid'); setSaving(false); return; }
      await guardrailService.create({ ...form, config_json: configJson });
      setShowCreate(false);
      setForm(DEFAULT_FORM);
      refresh();
    } catch (err) {
      setFormError(err?.response?.data?.detail || 'Failed to create guardrail');
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(g) {
    try {
      await guardrailService.update(g.id, { is_active: !g.is_active });
      refresh();
    } catch {}
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await guardrailService.delete(deleteTarget.id);
      setDeleteTarget(null);
      refresh();
    } catch {}
  }

  async function handleTest() {
    if (!testInput.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await guardrailService.test({
        messages: [{ role: 'user', content: testInput }],
      });
      setTestResult(result);
    } catch (err) {
      setTestResult({ triggered: true, triggered_by: [err?.response?.data?.detail || 'Error'], processed_messages: [] });
    } finally {
      setTesting(false);
    }
  }

  if (isLoading) return <div className="flex items-center justify-center py-20"><LoadingSpinner size="lg" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--ral-white)]">Guardrails</h2>
          <p className="text-sm text-[var(--ral-grey-light)]">Content filtering applied before/after every LLM call</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowTest(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--ral-border)] text-[var(--ral-grey-light)] hover:text-[var(--ral-white)] hover:border-[var(--ral-rust-core)] text-sm transition-colors"
          >
            <TestTube size={15} /> Test
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--ral-rust-core)] hover:bg-[var(--ral-rust-bright)] text-white text-sm font-medium transition-colors"
          >
            <Plus size={15} /> Add Guardrail
          </button>
        </div>
      </div>

      <ErrorBanner message={error} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(guardrails || []).map((g) => (
          <div key={g.id} className={`glass-panel p-5 rounded-lg border-l-4 transition-colors ${g.is_active ? 'border-l-[var(--ral-cyan)]' : 'border-l-[var(--ral-grey-mid)]'}`}>
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <Shield size={16} className={g.is_active ? 'text-[var(--ral-cyan)]' : 'text-[var(--ral-grey-mid)]'} />
                <h3 className="text-sm font-semibold text-[var(--ral-white)]">{g.name}</h3>
              </div>
              <div className="flex gap-1">
                <button onClick={() => handleToggle(g)} className="text-xs px-2 py-0.5 rounded border border-[var(--ral-border)] text-[var(--ral-grey-light)] hover:text-[var(--ral-white)]">
                  {g.is_active ? 'Disable' : 'Enable'}
                </button>
                <button onClick={() => setDeleteTarget(g)} className="p-1 text-[var(--ral-grey-mid)] hover:text-red-400">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className={`px-2 py-0.5 rounded font-mono ${TYPE_BADGE_COLORS[g.guardrail_type] || 'bg-[var(--bg-element)] text-[var(--ral-grey-light)]'}`}>
                {g.guardrail_type}
              </span>
              <span className="px-2 py-0.5 rounded bg-[var(--bg-element)] text-[var(--ral-grey-light)]">
                applies to: {g.applies_to}
              </span>
              <span className={`px-2 py-0.5 rounded font-mono ${g.action_on_trigger === 'block' ? 'badge-red' : 'badge-yellow'}`}>
                {g.action_on_trigger}
              </span>
            </div>
            {g.config_json && Object.keys(g.config_json).length > 0 && (
              <pre className="mt-3 text-[10px] text-[var(--ral-grey-mid)] font-mono bg-[var(--ral-black)] p-2 rounded overflow-x-auto">
                {JSON.stringify(g.config_json, null, 2)}
              </pre>
            )}
          </div>
        ))}
        {(!guardrails || guardrails.length === 0) && (
          <div className="col-span-2 glass-panel p-8 rounded-lg text-center text-sm text-[var(--ral-grey-mid)]">
            No guardrails configured. Add one to start filtering content.
          </div>
        )}
      </div>

      {showCreate && (
        <FormModal title="Add Guardrail" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate}>
            <ErrorBanner message={formError} />
            <Field label="Name"><Input value={form.name} onChange={e => setForm(f => ({...f, name: e.target.value}))} placeholder="Block competitor names" required /></Field>
            <Field label="Type">
              <Select value={form.guardrail_type} onChange={e => setForm(f => ({...f, guardrail_type: e.target.value}))}>
                {GUARDRAIL_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </Select>
              <p className="text-xs text-[var(--ral-grey-mid)] mt-1">
                {GUARDRAIL_TYPES.find(t => t.value === form.guardrail_type)?.hint}
              </p>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Applies To">
                <Select value={form.applies_to} onChange={e => setForm(f => ({...f, applies_to: e.target.value}))}>
                  <option value="both">Both</option>
                  <option value="input">Input only</option>
                  <option value="output">Output only</option>
                </Select>
              </Field>
              <Field label="On Trigger">
                <Select value={form.action_on_trigger} onChange={e => setForm(f => ({...f, action_on_trigger: e.target.value}))}>
                  <option value="block">Block</option>
                  <option value="redact">Redact</option>
                  <option value="flag">Flag only</option>
                </Select>
              </Field>
            </div>
            <Field label="Config JSON" hint="Leave {} for PII redaction — see type hint above">
              <textarea
                value={form.config_json}
                onChange={e => setForm(f => ({...f, config_json: e.target.value}))}
                rows={4}
                className="w-full bg-[var(--bg-element)] border border-[var(--border-element)] rounded-lg px-3 py-2 text-sm text-[var(--ral-white)] font-mono focus:outline-none focus:border-[var(--ral-rust-core)] transition-colors"
              />
            </Field>
            <FormActions onCancel={() => setShowCreate(false)} submitLabel="Add Guardrail" loading={saving} />
          </form>
        </FormModal>
      )}

      {showTest && (
        <FormModal title="Test Guardrails" onClose={() => { setShowTest(false); setTestResult(null); setTestInput(''); }}>
          <Field label="Test Input">
            <textarea
              value={testInput}
              onChange={e => setTestInput(e.target.value)}
              rows={4}
              placeholder="Enter a message to test against all active guardrails…"
              className="w-full bg-[var(--bg-element)] border border-[var(--border-element)] rounded-lg px-3 py-2 text-sm text-[var(--ral-white)] focus:outline-none focus:border-[var(--ral-rust-core)] transition-colors"
            />
          </Field>
          <button
            onClick={handleTest}
            disabled={testing || !testInput.trim()}
            className="px-4 py-2 rounded-lg bg-[var(--ral-rust-core)] hover:bg-[var(--ral-rust-bright)] disabled:opacity-50 text-white text-sm font-medium mb-4"
          >
            {testing ? 'Testing…' : 'Run Test'}
          </button>
          {testResult && (
            <div className={`p-4 rounded-lg border ${testResult.triggered ? 'alert-red' : 'alert-green'}`}>
              <div className="flex items-center gap-2 mb-2">
                {testResult.triggered
                  ? <XCircle size={16} className="icon-danger" />
                  : <CheckCircle size={16} className="icon-success" />
                }
                <span className={`text-sm font-semibold ${testResult.triggered ? 'text-danger' : 'text-success'}`}>
                  {testResult.triggered ? 'BLOCKED / MODIFIED' : 'PASSED'}
                </span>
              </div>
              {testResult.triggered_by?.length > 0 && (
                <p className="text-xs text-danger">Triggered by: {testResult.triggered_by.join(', ')}</p>
              )}
              {testResult.processed_messages?.length > 0 && (
                <pre className="mt-2 text-xs text-[var(--ral-grey-light)] font-mono bg-[var(--ral-black)] p-2 rounded overflow-x-auto">
                  {JSON.stringify(testResult.processed_messages, null, 2)}
                </pre>
              )}
            </div>
          )}
        </FormModal>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Delete Guardrail"
          message={`Delete guardrail "${deleteTarget.name}"?`}
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
};

export default GuardrailsView;
