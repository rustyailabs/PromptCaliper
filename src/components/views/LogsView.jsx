import React, { useState, useCallback } from 'react';
import { Search, ChevronDown, ChevronUp, Eye, RefreshCw } from 'lucide-react';
import Badge from '../shared/Badge';
import PromptModal from '../shared/PromptModal';
import LoadingSpinner from '../shared/LoadingSpinner';
import ErrorBanner from '../shared/ErrorBanner';
import { usePolling } from '../../hooks/usePolling';
import { logService } from '../../services/logService';

const STATUS_OPTIONS = [
  { label: 'All Status', value: '' },
  { label: '200 OK', value: '200' },
  { label: '429 Rate Limited', value: '429' },
];

const LogsView = ({ onViewPrompt }) => {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [cacheFilter, setCacheFilter] = useState('');
  const [page, setPage] = useState(1);
  const [expandedRow, setExpandedRow] = useState(null);
  const [selectedLog, setSelectedLog] = useState(null);

  const fetchLogs = useCallback(() => {
    const params = { page, limit: 50 };
    if (statusFilter) params.status_code = parseInt(statusFilter);
    if (cacheFilter === 'hit') params.cache_hit = true;
    if (cacheFilter === 'miss') params.cache_hit = false;
    if (search) params.search = search;
    return logService.getLogs(params);
  }, [page, statusFilter, cacheFilter, search]);

  const { data, isLoading, error, refresh } = usePolling(fetchLogs, 30000);
  const logs = data?.items || [];
  const total = data?.total || 0;

  function statusCode(log) {
    if (log.status_code === 200) return '200';
    if (log.status_code === 429) return '429';
    return 'error';
  }

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ral-grey-mid)]" size={14} />
          <input
            type="text"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search request ID…"
            className="w-full bg-[var(--bg-element)] border border-[var(--border-element)] rounded-md pl-9 pr-3 py-1.5 text-sm text-[var(--ral-white)] focus:border-[var(--ral-rust-core)] focus:outline-none"
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
          className="bg-[var(--bg-element)] border border-[var(--border-element)] rounded-md px-3 py-1.5 text-sm text-[var(--ral-white)] focus:outline-none"
        >
          {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select
          value={cacheFilter}
          onChange={e => { setCacheFilter(e.target.value); setPage(1); }}
          className="bg-[var(--bg-element)] border border-[var(--border-element)] rounded-md px-3 py-1.5 text-sm text-[var(--ral-white)] focus:outline-none"
        >
          <option value="">All Cache</option>
          <option value="hit">Cache Hit</option>
          <option value="miss">Cache Miss</option>
        </select>
        <button onClick={refresh} className="p-1.5 text-[var(--ral-grey-mid)] hover:text-[var(--ral-white)] transition-colors" title="Refresh">
          <RefreshCw size={16} />
        </button>
        <span className="text-xs text-[var(--ral-grey-mid)]">{total.toLocaleString()} total · Live 30s</span>
      </div>

      <ErrorBanner message={error} />

      {isLoading && logs.length === 0 ? (
        <div className="flex items-center justify-center py-16"><LoadingSpinner size="lg" /></div>
      ) : (
        <div className="glass-panel rounded-lg overflow-hidden border border-[var(--ral-border)]">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-element)]">
                  {['', 'Time', 'Model', 'Tokens', 'Cost', 'Latency', 'Cache', 'Status', 'Action'].map(h => (
                    <th key={h} className="py-3 px-4 text-[10px] font-bold uppercase tracking-wider text-[var(--ral-grey-mid)]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.length === 0 ? (
                  <tr><td colSpan={9} className="py-8 text-center text-xs text-[var(--ral-grey-mid)]">No logs found</td></tr>
                ) : (
                  logs.map((log) => (
                    <React.Fragment key={log.id}>
                      <tr
                        className="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] cursor-pointer"
                        onClick={() => setExpandedRow(expandedRow === log.id ? null : log.id)}
                      >
                        <td className="py-3 px-3 text-[var(--ral-grey-mid)]">
                          {expandedRow === log.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </td>
                        <td className="py-3 px-4 font-mono text-xs text-[var(--ral-grey-light)]">
                          {log.started_at?.slice(11, 19)}
                        </td>
                        <td className="py-3 px-4 text-xs text-[var(--ral-white)] max-w-[120px] truncate">{log.model}</td>
                        <td className="py-3 px-4 font-mono text-xs text-[var(--ral-grey-light)]">{log.total_tokens?.toLocaleString()}</td>
                        <td className="py-3 px-4 font-mono text-xs text-[var(--ral-rust-bright)]">${(log.cost_usd || 0).toFixed(5)}</td>
                        <td className="py-3 px-4 font-mono text-xs text-[var(--ral-grey-light)]">{log.latency_ms ? `${log.latency_ms}ms` : '—'}</td>
                        <td className="py-3 px-4 text-xs text-[var(--ral-grey-mid)]">{log.cache_hit ? '✓ Hit' : '—'}</td>
                        <td className="py-3 px-4"><Badge status={statusCode(log)} /></td>
                        <td className="py-3 px-4">
                          <button
                            onClick={e => { e.stopPropagation(); setSelectedLog(log); }}
                            className="p-1.5 text-[var(--ral-grey-mid)] hover:text-[var(--ral-rust-bright)]"
                          >
                            <Eye size={15} />
                          </button>
                        </td>
                      </tr>
                      {expandedRow === log.id && (
                        <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-element)]">
                          <td colSpan={9} className="px-8 py-4">
                            <div className="grid grid-cols-2 gap-6">
                              <div>
                                <p className="text-[10px] font-bold text-[var(--ral-grey-mid)] uppercase tracking-wider mb-2">Prompt</p>
                                <pre className="text-xs text-[var(--ral-grey-light)] whitespace-pre-wrap font-mono bg-[var(--ral-black)] p-3 rounded max-h-32 overflow-y-auto">
                                  {JSON.stringify(log.prompt_messages, null, 2)}
                                </pre>
                              </div>
                              <div>
                                <p className="text-[10px] font-bold text-[var(--ral-grey-mid)] uppercase tracking-wider mb-2">Response</p>
                                <pre className="text-xs text-[var(--ral-grey-light)] whitespace-pre-wrap font-mono bg-[var(--ral-black)] p-3 rounded max-h-32 overflow-y-auto">
                                  {log.response_content || log.error_message || '—'}
                                </pre>
                              </div>
                            </div>
                            <div className="mt-3 flex gap-6 text-xs text-[var(--ral-grey-mid)]">
                              <span>ID: <span className="font-mono text-[var(--ral-grey-light)]">{log.request_id}</span></span>
                              <span>Prompt tokens: <span className="font-mono">{log.prompt_tokens}</span></span>
                              <span>Completion tokens: <span className="font-mono">{log.completion_tokens}</span></span>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {total > 50 && (
            <div className="p-4 border-t border-[var(--border-subtle)] flex items-center justify-between">
              <span className="text-xs text-[var(--ral-grey-mid)]">Page {page} of {Math.ceil(total / 50)}</span>
              <div className="flex gap-2">
                <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="px-3 py-1 text-xs rounded border border-[var(--ral-border)] text-[var(--ral-grey-light)] disabled:opacity-40 hover:border-[var(--ral-rust-core)]">Prev</button>
                <button disabled={page * 50 >= total} onClick={() => setPage(p => p + 1)} className="px-3 py-1 text-xs rounded border border-[var(--ral-border)] text-[var(--ral-grey-light)] disabled:opacity-40 hover:border-[var(--ral-rust-core)]">Next</button>
              </div>
            </div>
          )}
        </div>
      )}

      {selectedLog && <PromptModal log={selectedLog} onClose={() => setSelectedLog(null)} />}
    </div>
  );
};

export default LogsView;
