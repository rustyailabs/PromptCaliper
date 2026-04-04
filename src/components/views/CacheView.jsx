import React, { useState } from 'react';
import { Database, Zap, Trash2, RefreshCw, Save } from 'lucide-react';
import LoadingSpinner from '../shared/LoadingSpinner';
import ErrorBanner from '../shared/ErrorBanner';
import { Field, Input, Select } from '../shared/FormModal';
import { usePolling } from '../../hooks/usePolling';
import { cacheService } from '../../services/cacheService';

const CACHE_TYPE_HINTS = {
  none: 'Caching disabled. Every request goes to the LLM provider.',
  local: 'In-memory cache (single process). Fast but lost on restart. Dev only.',
  redis: 'Exact-match Redis cache. Shared across processes. Production ready.',
  'redis-semantic': 'Semantic similarity cache using embeddings. Matches near-duplicate prompts.',
};

const CacheView = () => {
  const { data: config, isLoading, error, refresh } = usePolling(cacheService.getConfig, 30000);
  const { data: stats, refresh: refreshStats } = usePolling(cacheService.getStats, 30000);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [clearing, setClearing] = useState(false);

  // Sync form with loaded config (only once)
  React.useEffect(() => {
    if (config && !form) {
      setForm({
        cache_type: config.cache_type || 'none',
        redis_url: config.redis_url || '',
        ttl_seconds: config.ttl_seconds ?? 3600,
        semantic_similarity_threshold: config.semantic_similarity_threshold ?? 0.95,
        is_enabled: config.is_enabled ?? false,
      });
    }
  }, [config, form]);

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setSaveError('');
    try {
      await cacheService.updateConfig({
        ...form,
        ttl_seconds: parseInt(form.ttl_seconds),
        semantic_similarity_threshold: parseFloat(form.semantic_similarity_threshold),
      });
      refresh();
    } catch (err) {
      setSaveError(err?.response?.data?.detail || 'Failed to save cache config');
    } finally {
      setSaving(false);
    }
  }

  async function handleClear() {
    setClearing(true);
    try {
      await cacheService.clear();
      refreshStats();
    } catch {}
    finally { setClearing(false); }
  }

  if (isLoading || !form) return <div className="flex items-center justify-center py-20"><LoadingSpinner size="lg" /></div>;

  const isRedis = form.cache_type === 'redis' || form.cache_type === 'redis-semantic';
  const isSemantic = form.cache_type === 'redis-semantic';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--ral-white)]">Cache</h2>
          <p className="text-sm text-[var(--ral-grey-light)]">LiteLLM response caching — exact match and semantic</p>
        </div>
        <button
          onClick={handleClear}
          disabled={clearing || form.cache_type === 'none'}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--ral-border)] text-[var(--ral-grey-light)] hover:text-red-400 hover:border-red-500/40 text-sm transition-colors disabled:opacity-40"
        >
          <Trash2 size={15} /> {clearing ? 'Clearing…' : 'Clear Cache'}
        </button>
      </div>

      <ErrorBanner message={error} />

      {/* Live Runtime Status */}
      {stats && (
        <div className="flex items-center gap-4 px-4 py-3 rounded-lg bg-[var(--bg-element)] border border-[var(--border-element)] text-xs">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${stats.enabled ? 'bg-green-400' : 'bg-[var(--ral-grey-mid)]'}`} />
            <span className="text-[var(--ral-grey-mid)]">Runtime Status:</span>
            <span className={`font-mono font-semibold ${stats.enabled ? 'text-success' : 'text-[var(--ral-grey-light)]'}`}>
              {stats.enabled ? 'ACTIVE' : 'INACTIVE'}
            </span>
          </div>
          <span className="text-[var(--ral-grey-mid)]">|</span>
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--ral-grey-mid)]">Type:</span>
            <span className="font-mono text-[var(--ral-cyan)]">{stats.cache_type || 'none'}</span>
          </div>
          <span className="text-[var(--ral-grey-mid)]">|</span>
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--ral-grey-mid)]">Cached Entries:</span>
            <span className="font-mono text-[var(--ral-white)]">{stats.entry_count ?? 0}</span>
          </div>
          <button onClick={refreshStats} className="ml-auto text-[var(--ral-grey-mid)] hover:text-[var(--ral-white)] transition-colors">
            <RefreshCw size={13} />
          </button>
        </div>
      )}

      {/* Stats Row */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Hit Rate', value: `${stats.hit_rate_pct ?? 0}%`, color: 'var(--ral-cyan)' },
            { label: 'Total Hits', value: (stats.total_hits ?? 0).toLocaleString(), color: 'var(--ral-rust-core)' },
            { label: 'Total Misses', value: (stats.total_misses ?? 0).toLocaleString(), color: 'var(--ral-grey-light)' },
            { label: 'Estimated Savings', value: `$${parseFloat(stats.estimated_savings_usd ?? 0).toFixed(4)}`, color: 'var(--ral-rust-bright)' },
          ].map(({ label, value, color }) => (
            <div key={label} className="glass-panel p-4 rounded-lg" style={{ borderLeftWidth: 3, borderLeftColor: color, borderLeftStyle: 'solid' }}>
              <p className="text-[10px] uppercase tracking-wider text-[var(--ral-grey-mid)] mb-1">{label}</p>
              <p className="text-xl font-bold text-[var(--ral-white)]">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Config Form */}
      <div className="glass-panel p-6 rounded-lg">
        <h3 className="text-sm font-semibold text-[var(--ral-white)] mb-4 flex items-center gap-2">
          <Database size={15} className="text-[var(--ral-rust-core)]" /> Cache Configuration
        </h3>
        <ErrorBanner message={saveError} />
        <form onSubmit={handleSave} className="space-y-4">
          <div className="flex items-center gap-3 p-3 rounded-lg bg-[var(--bg-element)] border border-[var(--border-element)]">
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_enabled}
                onChange={e => setForm(f => ({ ...f, is_enabled: e.target.checked }))}
                className="sr-only peer"
              />
              <div className="w-10 h-5 bg-[var(--ral-grey-mid)] rounded-full peer peer-checked:bg-[var(--ral-rust-core)] transition-colors" />
              <div className="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5" />
            </label>
            <span className="text-sm text-[var(--ral-white)]">Enable Caching</span>
            <span className={`ml-auto text-xs font-mono px-2 py-0.5 rounded ${form.is_enabled ? 'badge-green' : 'bg-[var(--bg-element)] text-[var(--ral-grey-mid)]'}`}>
              {form.is_enabled ? 'ACTIVE' : 'DISABLED'}
            </span>
          </div>

          <Field label="Cache Type">
            <Select value={form.cache_type} onChange={e => setForm(f => ({ ...f, cache_type: e.target.value }))}>
              <option value="none">None (disabled)</option>
              <option value="local">Local (in-memory)</option>
              <option value="redis">Redis (exact match)</option>
              <option value="redis-semantic">Redis Semantic</option>
            </Select>
            <p className="text-xs text-[var(--ral-grey-mid)] mt-1">{CACHE_TYPE_HINTS[form.cache_type]}</p>
          </Field>

          {isRedis && (
            <Field label="Redis URL">
              <Input
                value={form.redis_url}
                onChange={e => setForm(f => ({ ...f, redis_url: e.target.value }))}
                placeholder="redis://localhost:6379/0"
              />
            </Field>
          )}

          <div className="grid grid-cols-2 gap-4">
            <Field label="TTL (seconds)">
              <Input
                type="number"
                value={form.ttl_seconds}
                onChange={e => setForm(f => ({ ...f, ttl_seconds: e.target.value }))}
                placeholder="3600"
              />
            </Field>
            {isSemantic && (
              <Field label="Similarity Threshold (0–1)">
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  value={form.semantic_similarity_threshold}
                  onChange={e => setForm(f => ({ ...f, semantic_similarity_threshold: e.target.value }))}
                  placeholder="0.95"
                />
              </Field>
            )}
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--ral-rust-core)] hover:bg-[var(--ral-rust-bright)] disabled:opacity-50 text-white text-sm font-medium transition-colors"
            >
              <Save size={14} /> {saving ? 'Saving…' : 'Save Config'}
            </button>
          </div>
        </form>
      </div>

      {/* How it works */}
      <div className="glass-panel p-5 rounded-lg">
        <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--ral-grey-mid)] mb-3">How LiteLLM Caching Works</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-[var(--ral-grey-light)]">
          <div>
            <p className="font-semibold text-[var(--ral-white)] mb-1 flex items-center gap-1.5"><Zap size={12} className="text-[var(--ral-cyan)]" /> Exact Match</p>
            <p>Caches responses by hashing the full messages array + model. Identical requests return instantly without hitting the provider.</p>
          </div>
          <div>
            <p className="font-semibold text-[var(--ral-white)] mb-1 flex items-center gap-1.5"><Zap size={12} className="text-[var(--ral-rust-core)]" /> Semantic Match</p>
            <p>Uses embeddings to match semantically similar (not just identical) prompts. Controlled by the similarity threshold — higher = more strict.</p>
          </div>
          <div>
            <p className="font-semibold text-[var(--ral-white)] mb-1 flex items-center gap-1.5"><Zap size={12} className="text-[var(--ral-rust-bright)]" /> Cost Savings</p>
            <p>Cache hits skip the LLM provider entirely. Savings estimated from the cost of the original cached response's token count.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CacheView;
