import { DollarSign, Database, Zap, Filter, Key, Tag, Hash } from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, Legend, PieChart, Pie, Cell
} from 'recharts';
import LoadingSpinner from '../shared/LoadingSpinner';
import { usePolling } from '../../hooks/usePolling';
import { analyticsService } from '../../services/analyticsService';
import { virtualKeyService } from '../../services/virtualKeyService';

const COLORS = ['var(--ral-rust-core)', 'var(--ral-cyan)', 'var(--ral-rust-bright)', 'var(--ral-grey-light)', '#a78bfa', '#34d399', '#fbbf24', '#f87171'];

const BREAKDOWN_OPTIONS = [
  { value: 'client_service_tag', label: 'Service Tag', icon: Tag },
  { value: 'session_id', label: 'Session ID', icon: Hash },
  { value: 'virtual_key_id', label: 'Virtual Key', icon: Key },
];

const AnalyticsView = ({ timeRange = '24h' }) => {
  const { data: overview, error: overviewError, refresh: refreshOverview } =
    usePolling(() => analyticsService.getOverview(timeRange), 30000);
  const { data: teamHistory, isLoading: loadingTeam, error: teamError } =
    usePolling(() => analyticsService.getTeamSpendHistory(6), 30000);
  const { data: tokenData, isLoading: loadingTokens, error: tokenError } =
    usePolling(() => analyticsService.getTokenEconomics(7), 30000);
  const { data: modelDist, isLoading: loadingPie, error: modelError, refresh: refreshModel } =
    usePolling(() => analyticsService.getModelDistribution(timeRange), 30000);

  const [breakdownBy, setBreakdownBy] = useState('client_service_tag');
  const [filterKeyId, setFilterKeyId] = useState(null);
  const [virtualKeys, setVirtualKeys] = useState([]);

  // Fetch virtual keys for the filter dropdown
  useEffect(() => {
    virtualKeyService.list().then(keys => setVirtualKeys(keys || [])).catch(() => {});
  }, []);

  const { data: breakdownData, isLoading: loadingBreakdown, error: breakdownError, refresh: refreshBreakdown } =
    usePolling(() => analyticsService.getBreakdown(breakdownBy, timeRange, filterKeyId), 30000);

  useEffect(() => {
    refreshOverview();
    refreshModel();
    refreshBreakdown();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeRange, breakdownBy, filterKeyId]);

  const teamNames = teamHistory
    ? [...new Set(teamHistory.flatMap(r => Object.keys(r).filter(k => k !== 'month')))]
    : [];

  // Compute summary stats for breakdown
  const breakdownSummary = (breakdownData || []).reduce((acc, item) => ({
    totalRequests: acc.totalRequests + item.request_count,
    totalCost: acc.totalCost + item.cost_usd,
    totalTokens: acc.totalTokens + item.total_tokens,
    uniqueGroups: acc.uniqueGroups + 1,
  }), { totalRequests: 0, totalCost: 0, totalTokens: 0, uniqueGroups: 0 });

  return (
    <div className="space-y-6 animate-fade-in">
      {overviewError && (
        <div className="text-xs text-[var(--ral-grey-mid)] px-1">{overviewError}</div>
      )}
      {/* KPI Header */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-panel p-5 rounded-lg border-l-4 border-l-[var(--ral-rust-core)] flex justify-between items-center">
          <div>
            <p className="text-xs text-[var(--ral-grey-mid)] uppercase tracking-wider">Total Cost ({timeRange})</p>
            <p className="text-2xl font-bold text-[var(--ral-white)] mt-1">
              ${(overview?.total_cost_usd ?? 0).toFixed(4)}
            </p>
          </div>
          <DollarSign size={28} className="text-[var(--ral-rust-core)] opacity-60" />
        </div>
        <div className="glass-panel p-5 rounded-lg border-l-4 border-l-[var(--ral-cyan)] flex justify-between items-center">
          <div>
            <p className="text-xs text-[var(--ral-grey-mid)] uppercase tracking-wider">Total Tokens</p>
            <p className="text-2xl font-bold text-[var(--ral-white)] mt-1">
              {(overview?.total_tokens ?? 0).toLocaleString()}
            </p>
          </div>
          <Database size={28} className="text-[var(--ral-cyan)] opacity-60" />
        </div>
        <div className="glass-panel p-5 rounded-lg border-l-4 border-l-[var(--ral-rust-bright)] flex justify-between items-center">
          <div>
            <p className="text-xs text-[var(--ral-grey-mid)] uppercase tracking-wider">Cache Hit Rate</p>
            <p className="text-2xl font-bold text-[var(--ral-white)] mt-1">
              {overview?.cache_hit_rate ?? 0}%
            </p>
          </div>
          <Zap size={28} className="text-[var(--ral-rust-bright)] opacity-60" />
        </div>
      </div>

      {/* Team Spend + Token Economics */}
      <div className="grid grid-cols-2 gap-6">
        <div className="glass-panel p-6 rounded-lg">
          <div className="mb-4">
            <h3 className="text-[var(--ral-white)] font-semibold">Org Monthly Spend by Team</h3>
            <p className="text-xs text-[var(--ral-grey-light)]">Last 6 months</p>
          </div>
          {loadingTeam ? (
            <div className="h-56 flex items-center justify-center"><LoadingSpinner /></div>
          ) : teamError ? (
            <div className="h-56 flex items-center justify-center text-xs text-[var(--ral-grey-mid)]">{teamError}</div>
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={teamHistory || []} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                  <XAxis dataKey="month" stroke="var(--ral-grey-mid)" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="var(--ral-grey-mid)" fontSize={11} tickLine={false} axisLine={false} tickFormatter={v => `$${v}`} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--ral-grey-dark)', borderColor: 'var(--ral-rust-core)', borderRadius: 6 }}
                    labelStyle={{ color: 'var(--ral-grey-mid)', fontSize: 11 }}
                    itemStyle={{ color: 'var(--ral-white)' }}
                    formatter={v => [`$${parseFloat(v).toFixed(4)}`]}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, color: 'var(--ral-grey-light)' }} />
                  {teamNames.map((team, i) => (
                    <Bar key={team} dataKey={team} stackId="a" fill={COLORS[i % COLORS.length]} radius={i === teamNames.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="glass-panel p-6 rounded-lg">
          <div className="mb-4">
            <h3 className="text-[var(--ral-white)] font-semibold">Token Economics (7d)</h3>
            <p className="text-xs text-[var(--ral-grey-light)]">Input vs output token split</p>
          </div>
          {loadingTokens ? (
            <div className="h-56 flex items-center justify-center"><LoadingSpinner /></div>
          ) : tokenError ? (
            <div className="h-56 flex items-center justify-center text-xs text-[var(--ral-grey-mid)]">{tokenError}</div>
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={tokenData || []} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                  <defs>
                    <linearGradient id="gradIn" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--ral-rust-core)" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="var(--ral-rust-core)" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradOut" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--ral-cyan)" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="var(--ral-cyan)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                  <XAxis dataKey="day" stroke="var(--ral-grey-mid)" fontSize={11} tickLine={false} axisLine={false} tickFormatter={d => d?.slice(5)} />
                  <YAxis stroke="var(--ral-grey-mid)" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--ral-grey-dark)', borderColor: 'var(--ral-rust-core)', borderRadius: 6 }}
                    labelStyle={{ color: 'var(--ral-grey-mid)', fontSize: 11 }}
                    itemStyle={{ color: 'var(--ral-white)' }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, color: 'var(--ral-grey-light)' }} />
                  <Area type="monotone" dataKey="input_tokens" name="Input" stroke="var(--ral-rust-core)" fill="url(#gradIn)" strokeWidth={2} />
                  <Area type="monotone" dataKey="output_tokens" name="Output" stroke="var(--ral-cyan)" fill="url(#gradOut)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* Model cost distribution pie */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-1 glass-panel p-6 rounded-lg">
          <h3 className="text-[var(--ral-white)] font-semibold mb-4">Cost by Model</h3>
          {loadingPie ? (
            <div className="h-48 flex items-center justify-center"><LoadingSpinner /></div>
          ) : modelError ? (
            <div className="h-48 flex items-center justify-center text-xs text-[var(--ral-grey-mid)]">{modelError}</div>
          ) : (
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={modelDist || []} dataKey="cost_usd" nameKey="model" cx="50%" cy="50%" outerRadius={70} label={({ name, percent }) => `${name?.split('/').pop()} ${(percent * 100).toFixed(0)}%`} labelLine={false} fontSize={10}>
                    {(modelDist || []).map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--ral-grey-dark)', borderColor: 'var(--ral-rust-core)', borderRadius: 6 }}
                    labelStyle={{ color: 'var(--ral-grey-mid)', fontSize: 11 }}
                    itemStyle={{ color: 'var(--ral-white)' }}
                    formatter={v => [`$${parseFloat(v).toFixed(5)}`]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="col-span-2 glass-panel p-6 rounded-lg">
          <h3 className="text-[var(--ral-white)] font-semibold mb-4">Model Breakdown</h3>
          <div className="space-y-3">
            {(modelDist || []).slice(0, 6).map((m, i) => (
              <div key={m.model} className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                <span className="text-xs text-[var(--ral-grey-light)] flex-1 truncate">{m.model}</span>
                <span className="text-xs font-mono text-[var(--ral-white)]">{m.request_count} reqs</span>
                <span className="text-xs font-mono text-[var(--ral-rust-bright)]">${parseFloat(m.cost_usd || 0).toFixed(5)}</span>
                <div className="w-20 h-1.5 bg-[var(--bg-element)] rounded-full overflow-hidden">
                  <div className="h-full bg-[var(--ral-rust-core)]" style={{ width: `${m.pct}%` }} />
                </div>
                <span className="text-xs text-[var(--ral-grey-mid)] w-8 text-right">{m.pct}%</span>
              </div>
            ))}
            {(!modelDist || modelDist.length === 0) && (
              <p className="text-xs text-[var(--ral-grey-mid)]">No data yet — send requests through the gateway.</p>
            )}
          </div>
        </div>
      </div>

      {/* ── Service, Session & Key Breakdown ── */}
      <div className="glass-panel p-6 rounded-lg">
        {/* Header with controls */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
          <div>
            <h3 className="text-[var(--ral-white)] font-semibold text-base">Usage Breakdown</h3>
            <p className="text-xs text-[var(--ral-grey-light)] mt-0.5">Analyze usage by service tag, session, or virtual key</p>
          </div>
          <div className="flex flex-wrap gap-3 items-center">
            {/* Key filter dropdown */}
            <div className="flex items-center gap-1.5">
              <Filter size={12} className="text-[var(--ral-grey-mid)]" />
              <select
                id="breakdown-key-filter"
                value={filterKeyId ?? ''}
                onChange={(e) => setFilterKeyId(e.target.value ? Number(e.target.value) : null)}
                className="text-xs bg-[var(--bg-element)] text-[var(--ral-grey-light)] border border-[var(--border-element)] rounded px-2 py-1.5 outline-none focus:border-[var(--ral-rust-core)] transition-colors cursor-pointer"
                style={{ maxWidth: 200 }}
              >
                <option value="">All Keys</option>
                {virtualKeys.map(vk => (
                  <option key={vk.id} value={vk.id}>
                    {vk.key_prefix} {vk.owner_label ? `(${vk.owner_label})` : ''}
                  </option>
                ))}
              </select>
            </div>

            {/* Group-by toggles */}
            <div className="flex rounded-md overflow-hidden border border-[var(--border-element)]">
              {BREAKDOWN_OPTIONS.map(opt => {
                const Icon = opt.icon;
                const isActive = breakdownBy === opt.value;
                return (
                  <button
                    key={opt.value}
                    id={`breakdown-toggle-${opt.value}`}
                    onClick={() => setBreakdownBy(opt.value)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs transition-all ${
                      isActive
                        ? 'bg-[var(--ral-rust-core)] text-white font-medium'
                        : 'bg-[var(--bg-element)] text-[var(--ral-grey-light)] hover:text-white hover:bg-[var(--bg-overlay)]'
                    }`}
                  >
                    <Icon size={12} />
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Summary stat pills */}
        {!loadingBreakdown && !breakdownError && breakdownData?.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <div className="bg-[var(--bg-overlay)] rounded-md px-4 py-3 border border-[var(--border-subtle)]">
              <p className="text-[10px] text-[var(--ral-grey-mid)] uppercase tracking-wider">Groups</p>
              <p className="text-lg font-bold text-[var(--ral-white)] mt-0.5">{breakdownSummary.uniqueGroups}</p>
            </div>
            <div className="bg-[var(--bg-overlay)] rounded-md px-4 py-3 border border-[var(--border-subtle)]">
              <p className="text-[10px] text-[var(--ral-grey-mid)] uppercase tracking-wider">Total Requests</p>
              <p className="text-lg font-bold text-[var(--ral-white)] mt-0.5">{breakdownSummary.totalRequests.toLocaleString()}</p>
            </div>
            <div className="bg-[var(--bg-overlay)] rounded-md px-4 py-3 border border-[var(--border-subtle)]">
              <p className="text-[10px] text-[var(--ral-grey-mid)] uppercase tracking-wider">Total Cost</p>
              <p className="text-lg font-bold text-[var(--ral-rust-bright)] mt-0.5">${breakdownSummary.totalCost.toFixed(4)}</p>
            </div>
            <div className="bg-[var(--bg-overlay)] rounded-md px-4 py-3 border border-[var(--border-subtle)]">
              <p className="text-[10px] text-[var(--ral-grey-mid)] uppercase tracking-wider">Total Tokens</p>
              <p className="text-lg font-bold text-[var(--ral-cyan)] mt-0.5">{breakdownSummary.totalTokens.toLocaleString()}</p>
            </div>
          </div>
        )}

        {loadingBreakdown ? (
          <div className="h-64 flex items-center justify-center"><LoadingSpinner /></div>
        ) : breakdownError ? (
          <div className="h-64 flex items-center justify-center text-xs text-[var(--ral-grey-mid)]">{breakdownError}</div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Chart — cost + requests stacked */}
            <div className="lg:col-span-1 h-64">
              <p className="text-[10px] text-[var(--ral-grey-mid)] uppercase tracking-wider mb-2">Cost Distribution</p>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={(breakdownData || []).slice(0, 8)} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" horizontal={false} />
                  <XAxis type="number" stroke="var(--ral-grey-mid)" fontSize={10} tickLine={false} axisLine={false} tickFormatter={v => `$${v}`} />
                  <YAxis type="category" dataKey="key" stroke="var(--ral-grey-mid)" fontSize={9} tickLine={false} axisLine={false} width={90}
                    tickFormatter={v => v.length > 14 ? v.slice(0, 12) + '…' : v}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--ral-grey-dark)', borderColor: 'var(--ral-rust-core)', borderRadius: 6 }}
                    labelStyle={{ color: 'var(--ral-grey-mid)', fontSize: 11 }}
                    itemStyle={{ color: 'var(--ral-white)' }}
                    formatter={(v, name) => [name === 'Cost ($)' ? `$${parseFloat(v).toFixed(5)}` : v.toLocaleString()]}
                  />
                  <Bar dataKey="cost_usd" name="Cost ($)" fill="var(--ral-rust-core)" radius={[0, 4, 4, 0]} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Detailed list */}
            <div className="lg:col-span-2 space-y-2 max-h-72 overflow-y-auto pr-1">
              <div className="grid grid-cols-[auto_1fr_repeat(5,auto)] gap-x-3 gap-y-0 text-[10px] text-[var(--ral-grey-mid)] uppercase tracking-wider px-3 pb-2 border-b border-[var(--border-subtle)] sticky top-0 bg-[var(--bg-surface)] z-10">
                <span>#</span>
                <span>Name</span>
                <span className="text-right">Requests</span>
                <span className="text-right">Cost</span>
                <span className="text-right">Tokens</span>
                <span className="text-right">Latency</span>
                <span className="text-right">Share</span>
              </div>
              {(breakdownData || []).map((item, i) => {
                const maxRequests = Math.max(...(breakdownData || []).map(d => d.request_count), 1);
                return (
                  <div
                    key={item.key}
                    className="grid grid-cols-[auto_1fr_repeat(5,auto)] gap-x-3 items-center px-3 py-2.5 rounded-md bg-[var(--bg-overlay)] border border-[var(--border-subtle)] hover:border-[var(--ral-rust-core)] transition-colors group relative overflow-hidden"
                  >
                    {/* Activity bar background */}
                    <div
                      className="absolute inset-y-0 left-0 opacity-[0.06] transition-all"
                      style={{ width: `${(item.request_count / maxRequests) * 100}%`, backgroundColor: COLORS[i % COLORS.length] }}
                    />
                    <div className="w-5 h-5 rounded bg-[var(--bg-element)] flex items-center justify-center text-[10px] font-mono text-[var(--ral-grey-light)] relative z-[1]">
                      {i + 1}
                    </div>
                    <span className="text-xs text-[var(--ral-white)] font-medium truncate relative z-[1]" title={item.key}>
                      {item.key}
                    </span>
                    <span className="text-xs font-mono text-[var(--ral-grey-light)] text-right relative z-[1] tabular-nums">
                      {item.request_count.toLocaleString()}
                    </span>
                    <span className="text-xs font-mono text-[var(--ral-rust-bright)] text-right relative z-[1] tabular-nums">
                      ${parseFloat(item.cost_usd || 0).toFixed(5)}
                    </span>
                    <span className="text-xs font-mono text-[var(--ral-cyan)] text-right relative z-[1] tabular-nums" title={`Prompt: ${(item.prompt_tokens || 0).toLocaleString()} | Completion: ${(item.completion_tokens || 0).toLocaleString()}`}>
                      {(item.total_tokens || 0).toLocaleString()}
                    </span>
                    <span className="text-xs font-mono text-[var(--ral-grey-light)] text-right relative z-[1] tabular-nums">
                      {(item.avg_latency_ms || 0).toLocaleString()}ms
                    </span>
                    <div className="flex items-center gap-1.5 relative z-[1]">
                      <div className="w-16 h-1.5 bg-[var(--bg-element)] rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${item.pct_cost}%`, backgroundColor: COLORS[i % COLORS.length] }}
                        />
                      </div>
                      <span className="text-[10px] text-[var(--ral-grey-mid)] w-9 text-right tabular-nums">{item.pct_cost}%</span>
                    </div>
                  </div>
                );
              })}
              {(!breakdownData || breakdownData.length === 0) && (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="w-12 h-12 rounded-full bg-[var(--bg-element)] flex items-center justify-center mb-3">
                    <Filter size={20} className="text-[var(--ral-grey-mid)]" />
                  </div>
                  <p className="text-xs text-[var(--ral-grey-mid)]">No data for this view.</p>
                  <p className="text-[10px] text-[var(--ral-grey-mid)] mt-1">
                    Send requests with <code className="text-[var(--ral-rust-bright)]">X-Session-ID</code> or <code className="text-[var(--ral-rust-bright)]">X-Client-Service-Tag</code> headers.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalyticsView;

