import React, { useState } from 'react';
import { Zap, Lock, Settings, Plus, Trash2, ToggleRight, ToggleLeft } from 'lucide-react';
import Badge from '../shared/Badge';
import LoadingSpinner from '../shared/LoadingSpinner';
import ErrorBanner from '../shared/ErrorBanner';
import ConfirmDialog from '../shared/ConfirmDialog';
import FormModal, { Field, Input, FormActions } from '../shared/FormModal';
import { usePolling } from '../../hooks/usePolling';
import { modelService } from '../../services/modelService';

const PROVIDERS = [
  { id: 'openai',    label: 'OpenAI',    color: 'var(--ral-cyan)' },
  { id: 'anthropic', label: 'Anthropic', color: '#d97706' },
  { id: 'azure',     label: 'Azure',     color: '#3b82f6' },
  { id: 'gemini',    label: 'Gemini API', color: '#8b5cf6' },
  { id: 'vertex_ai', label: 'Vertex AI', color: '#a855f7' },
  { id: 'bedrock',   label: 'Bedrock',   color: '#f59e0b' },
  { id: 'ollama',    label: 'Ollama',    color: 'var(--ral-rust-core)' },
];

const PROVIDER_LABELS = Object.fromEntries(PROVIDERS.map((p) => [p.id, p.label]));

const DEFAULT_FORM = {
  display_name: '', litellm_model_name: '', provider: 'openai',
  api_key_env_var: '', api_base: '', routing_weight: 1,
  context_window: '', cost_per_input_token: '', cost_per_output_token: '',
};

const ModelConfigView = () => {
  const { data: models, isLoading, error, refresh } = usePolling(modelService.list, 30000);
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
      await modelService.create({
        ...form,
        routing_weight: parseInt(form.routing_weight) || 1,
        context_window: form.context_window ? parseInt(form.context_window) : null,
        cost_per_input_token: form.cost_per_input_token ? parseFloat(form.cost_per_input_token) : null,
        cost_per_output_token: form.cost_per_output_token ? parseFloat(form.cost_per_output_token) : null,
      });
      setShowCreate(false);
      setForm(DEFAULT_FORM);
      refresh();
    } catch (err) {
      setFormError(err?.response?.data?.detail || 'Failed to create model');
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(model) {
    try {
      await modelService.update(model.id, { is_active: !model.is_active });
      refresh();
    } catch {}
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await modelService.delete(deleteTarget.id);
      setDeleteTarget(null);
      refresh();
    } catch {}
  }

  if (isLoading) return <div className="flex items-center justify-center py-20"><LoadingSpinner size="lg" /></div>;

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} />

      {/* Global feature cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="glass-panel p-6 rounded-lg border-l-2 border-l-[var(--ral-rust-core)]">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-[rgba(192,83,26,0.1)] rounded-full text-[var(--ral-rust-core)]"><Zap size={24} /></div>
            <div>
              <h3 className="text-lg font-bold text-[var(--ral-white)]">Smart Routing</h3>
              <p className="text-sm text-[var(--ral-grey-light)] mt-1 mb-4">LiteLLM Router load-balances across all active models using {'"least-busy"'} strategy with automatic fallbacks.</p>
              <div className="flex items-center gap-2">
                <ToggleRight size={32} className="text-[var(--ral-rust-core)] cursor-pointer" />
                <span className="text-xs font-mono text-[var(--ral-cyan)]">ENABLED</span>
              </div>
            </div>
          </div>
        </div>
        <div className="glass-panel p-6 rounded-lg border-l-2 border-l-[var(--ral-cyan)]">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-[rgba(0,212,255,0.1)] rounded-full text-[var(--ral-cyan)]"><Lock size={24} /></div>
            <div>
              <h3 className="text-lg font-bold text-[var(--ral-white)]">PII Redaction</h3>
              <p className="text-sm text-[var(--ral-grey-light)] mt-1 mb-4">Configure PII guardrails in the Guardrails view to redact emails, SSNs, and phone numbers.</p>
              <div className="flex items-center gap-2">
                <ToggleLeft size={32} className="text-[var(--ral-grey-mid)] cursor-pointer" />
                <span className="text-xs font-mono text-[var(--ral-grey-mid)]">SEE GUARDRAILS</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Models list header */}
      <div className="flex items-center justify-between">
        <h3 className="text-[var(--ral-grey-light)] uppercase tracking-widest text-xs font-bold">
          Connected Models ({models?.length ?? 0})
        </h3>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--ral-rust-core)] hover:bg-[var(--ral-rust-bright)] text-white text-xs font-medium transition-colors"
        >
          <Plus size={14} /> Add Model
        </button>
      </div>

      {/* Models */}
      <div className="grid grid-cols-1 gap-4">
        {(models || []).map((model) => (
          <div key={model.id} className="glass-panel p-4 rounded-lg flex items-center justify-between hover:border-[var(--ral-grey-light)] transition-colors">
            <div className="flex items-center gap-4">
              <div className={`w-2 h-12 rounded-full ${model.is_active ? 'bg-[var(--ral-cyan)]' : 'bg-[var(--ral-grey-mid)]'}`} />
              <div>
                <h4 className="text-[var(--ral-white)] font-bold text-base">{model.display_name}</h4>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs px-2 py-0.5 rounded bg-[rgba(255,255,255,0.05)] text-[var(--ral-grey-light)]">
                    {PROVIDER_LABELS[model.provider] || model.provider}
                  </span>
                  <span className="text-xs text-[var(--ral-grey-mid)] font-mono">{model.litellm_model_name}</span>
                  {model.context_window && <span className="text-xs text-[var(--ral-grey-mid)] font-mono">{(model.context_window / 1000).toFixed(0)}k ctx</span>}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-8">
              {(model.cost_per_input_token || model.cost_per_output_token) && (
                <div className="text-right hidden md:block">
                  <div className="text-[10px] uppercase text-[var(--ral-grey-mid)]">Cost (In/Out)</div>
                  <div className="text-xs font-mono text-[var(--ral-white)]">
                    ${model.cost_per_input_token} / ${model.cost_per_output_token}
                  </div>
                </div>
              )}
              {model.avg_latency_ms && (
                <div className="text-right hidden md:block">
                  <div className="text-[10px] uppercase text-[var(--ral-grey-mid)]">Avg Latency</div>
                  <div className={`text-xs font-mono ${model.avg_latency_ms < 500 ? 'text-[var(--ral-cyan)]' : 'text-[var(--ral-rust-bright)]'}`}>
                    {model.avg_latency_ms}ms
                  </div>
                </div>
              )}
              <div className="text-right">
                <div className="text-[10px] uppercase text-[var(--ral-grey-mid)]">Weight</div>
                <div className="text-xs font-mono text-[var(--ral-white)]">{model.routing_weight}</div>
              </div>
              <Badge status={model.status} />
              <button onClick={() => handleToggle(model)} className="p-2 rounded hover:bg-[rgba(255,255,255,0.05)] text-[var(--ral-grey-mid)] hover:text-white" title={model.is_active ? 'Disable' : 'Enable'}>
                {model.is_active ? <ToggleRight size={18} className="text-[var(--ral-cyan)]" /> : <ToggleLeft size={18} />}
              </button>
              <button onClick={() => setDeleteTarget(model)} className="p-2 rounded hover:bg-[rgba(255,255,255,0.05)] text-[var(--ral-grey-mid)] hover:text-red-400">
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        ))}
        {(!models || models.length === 0) && (
          <div className="glass-panel p-8 rounded-lg text-center text-sm text-[var(--ral-grey-mid)]">
            No models configured. Add one to start routing requests.
          </div>
        )}
      </div>

      {/* Create modal */}
      {showCreate && (
        <FormModal title="Add Model" onClose={() => setShowCreate(false)}>
          <form onSubmit={handleCreate}>
            <ErrorBanner message={formError} />
            <Field label="Display Name"><Input value={form.display_name} onChange={e => setForm(f => ({...f, display_name: e.target.value}))} placeholder="GPT-4 Turbo" required /></Field>
            <Field label="LiteLLM Model Name" hint="e.g. gpt-4-turbo, azure/gpt-4-turbo, anthropic/claude-3-opus-20240229">
              <Input value={form.litellm_model_name} onChange={e => setForm(f => ({...f, litellm_model_name: e.target.value}))} placeholder="gpt-4-turbo" required />
            </Field>
            <Field label="Provider">
              <div className="flex flex-wrap gap-2">
                {PROVIDERS.map(p => {
                  const active = form.provider === p.id;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setForm(f => ({...f, provider: p.id}))}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all"
                      style={{
                        borderColor: active ? p.color : 'var(--border-element)',
                        background: active ? `color-mix(in srgb, ${p.color} 15%, transparent)` : 'var(--bg-element)',
                        color: active ? p.color : 'var(--ral-grey-light)',
                        boxShadow: active ? `0 0 8px color-mix(in srgb, ${p.color} 40%, transparent)` : 'none',
                      }}
                    >
                      {p.label}
                    </button>
                  );
                })}
              </div>
            </Field>
            <Field label="API Key Env Var (optional)" hint="Name of the env var holding the API key — leave blank for Vertex AI or local/Ollama models"><Input value={form.api_key_env_var} onChange={e => setForm(f => ({...f, api_key_env_var: e.target.value}))} placeholder="OPENAI_API_KEY" /></Field>
            <Field label="API Base (optional — for Azure/Ollama)"><Input value={form.api_base} onChange={e => setForm(f => ({...f, api_base: e.target.value}))} placeholder="https://your-azure.openai.azure.com" /></Field>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Routing Weight"><Input type="number" value={form.routing_weight} onChange={e => setForm(f => ({...f, routing_weight: e.target.value}))} min={1} /></Field>
              <Field label="Context Window"><Input type="number" value={form.context_window} onChange={e => setForm(f => ({...f, context_window: e.target.value}))} placeholder="128000" /></Field>
              <Field label="Cost/Input Token"><Input type="number" step="0.00000001" value={form.cost_per_input_token} onChange={e => setForm(f => ({...f, cost_per_input_token: e.target.value}))} placeholder="0.00001" /></Field>
            </div>
            <FormActions onCancel={() => setShowCreate(false)} submitLabel="Add Model" loading={saving} />
          </form>
        </FormModal>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Remove Model"
          message={`Remove "${deleteTarget.display_name}" from the gateway? Active requests will complete using other models.`}
          confirmLabel="Remove"
          danger
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
};

export default ModelConfigView;
