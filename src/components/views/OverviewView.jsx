import { Database, Eye, Activity, Clock, DollarSign, Zap, RefreshCw } from 'lucide-react';
import { useEffect } from 'react';
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts';
import StatCard from '../shared/StatCard';
import Badge from '../shared/Badge';
import LoadingSpinner from '../shared/LoadingSpinner';
import { usePolling } from '../../hooks/usePolling';
import { analyticsService } from '../../services/analyticsService';
import { logService } from '../../services/logService';

// Derive the best chart granularity from the selected time range
function granularityFor(timeRange) {
  return timeRange === '7d' ? 'day' : 'hour';
}

const FALLBACK_STATS = [
  { label: 'Total Requests', value: '—', trend: '', icon: Activity },
  { label: 'Avg Latency', value: '—', trend: '', icon: Clock },
  { label: 'Total Cost', value: '—', trend: '', icon: DollarSign },
  { label: 'Cache Hit Rate', value: '—', trend: '', icon: Zap },
];

function buildStats(overview) {
  if (!overview) return FALLBACK_STATS;
  return [
    { label: 'Total Requests', value: overview.total_requests?.toLocaleString() ?? '0', trend: '', icon: Activity },
    { label: 'Avg Latency', value: `${overview.avg_latency_ms ?? 0}ms`, trend: '', icon: Clock },
    { label: 'Total Cost', value: `$${(overview.total_cost_usd ?? 0).toFixed(4)}`, trend: '', icon: DollarSign },
    { label: 'Cache Hit Rate', value: `${overview.cache_hit_rate ?? 0}%`, trend: '', icon: Zap },
  ];
}

function buildChartData(timeseries, timeRange) {
  if (!timeseries?.length) return [];
  return timeseries.map(d => ({
    // Hourly buckets → "14h"; daily buckets → "Mar 05"
    time: d.time?.length > 10
      ? `${d.time.slice(11, 13)}h`
      : timeRange === '7d'
        ? new Date(d.time + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
        : d.time?.slice(0, 10),
    requests: d.requests,
    tokens: d.tokens || 0,
    cost_usd: parseFloat((d.cost_usd || 0).toFixed(5)),
  }));
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload || {};
  return (
    <div style={{ backgroundColor: 'var(--ral-grey-dark)', border: '1px solid var(--ral-rust-core)', borderRadius: 6, padding: '10px 14px', fontSize: 12 }}>
      <p style={{ color: 'var(--ral-grey-mid)', marginBottom: 6, fontFamily: 'monospace' }}>{label}</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span style={{ color: 'var(--ral-rust-bright)' }}>Requests: <strong>{d.requests?.toLocaleString()}</strong></span>
        <span style={{ color: 'var(--ral-cyan)' }}>Tokens: <strong>{d.tokens?.toLocaleString()}</strong></span>
        <span style={{ color: 'var(--ral-grey-light)' }}>Cost: <strong>${d.cost_usd?.toFixed(5)}</strong></span>
      </div>
    </div>
  );
}

const OverviewView = ({ onViewPrompt, timeRange = '24h' }) => {
  const { data: overview, refresh: refreshOverview } = usePolling(
    () => analyticsService.getOverview(timeRange),
    30000
  );
  const { data: timeseries, isLoading: loadingChart, refresh: refreshTimeseries } = usePolling(
    () => analyticsService.getTimeseries(timeRange, granularityFor(timeRange)),
    30000
  );
  const { data: modelDist, refresh: refreshModel } = usePolling(
    () => analyticsService.getModelDistribution(timeRange),
    30000
  );
  const { data: logsData } = usePolling(
    () => logService.getLogs({ limit: 5 }),
    30000
  );

  // Re-fetch time-range-sensitive data immediately when the prop changes
  useEffect(() => {
    refreshOverview();
    refreshTimeseries();
    refreshModel();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeRange]);

  const stats = buildStats(overview);
  const chartData = buildChartData(timeseries, timeRange);
  const recentLogs = logsData?.items || [];
  const models = modelDist || [];

  const COLORS = ['bg-[var(--ral-rust-core)]', 'bg-[var(--ral-rust-deep)]', 'bg-[var(--ral-cyan-dim)]', 'bg-[var(--ral-grey-light)]'];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, i) => (
          <StatCard key={i} {...stat} />
        ))}
      </div>

      {/* Chart + Model Distribution */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 glass-panel p-6 rounded-lg">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-[var(--ral-white)] font-semibold">Request & Token Activity</h3>
              <p className="text-xs text-[var(--ral-grey-light)]">
                Requests (bars) · Tokens (line) — last {timeRange} · {granularityFor(timeRange)}
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3 text-[10px] text-[var(--ral-grey-mid)]">
                <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm bg-[var(--ral-rust-core)]" />Requests</span>
                <span className="flex items-center gap-1"><span className="inline-block w-5 h-0.5 bg-[var(--ral-cyan)]" />Tokens</span>
              </div>
              <button onClick={refreshOverview} className="text-[var(--ral-grey-mid)] hover:text-[var(--ral-white)] transition-colors">
                <RefreshCw size={14} />
              </button>
            </div>
          </div>
          {loadingChart ? (
            <div className="h-64 flex items-center justify-center"><LoadingSpinner /></div>
          ) : chartData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-xs text-[var(--ral-grey-mid)]">No data for this time range</div>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                  <XAxis dataKey="time" stroke="var(--ral-grey-mid)" fontSize={11} tickLine={false} axisLine={false} interval={2} />
                  {/* Left axis — requests */}
                  <YAxis yAxisId="req" stroke="var(--ral-grey-mid)" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
                  {/* Right axis — tokens */}
                  <YAxis yAxisId="tok" orientation="right" stroke="var(--ral-grey-mid)" fontSize={11} tickLine={false} axisLine={false}
                    tickFormatter={v => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar yAxisId="req" dataKey="requests" fill="var(--ral-rust-core)" radius={[3, 3, 0, 0]} maxBarSize={32} opacity={0.85} />
                  <Line yAxisId="tok" type="monotone" dataKey="tokens" stroke="var(--ral-cyan)" strokeWidth={2} dot={{ r: 3, fill: 'var(--ral-cyan)', strokeWidth: 0 }} activeDot={{ r: 5 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Model Distribution */}
        <div className="col-span-1 glass-panel p-6 rounded-lg flex flex-col">
          <h3 className="text-[var(--ral-white)] font-semibold mb-6">Model Distribution</h3>
          {models.length === 0 ? (
            <p className="text-xs text-[var(--ral-grey-mid)] mt-4">No data yet</p>
          ) : (
            <div className="flex-1 space-y-4">
              {models.slice(0, 5).map((model, i) => (
                <div key={model.model}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-[var(--ral-grey-light)] truncate max-w-[120px]">{model.model}</span>
                    <span className="text-[var(--ral-white)] font-mono">{model.pct}%</span>
                  </div>
                  <div className="w-full h-2 bg-[var(--bg-element)] rounded-full overflow-hidden">
                    <div className={`h-full ${COLORS[i % COLORS.length]}`} style={{ width: `${model.pct}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Logs */}
      <div className="glass-panel rounded-lg overflow-hidden border border-[var(--ral-border)]">
        <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between bg-[var(--bg-element)]">
          <div className="flex items-center gap-3">
            <Database size={18} className="text-[var(--ral-grey-light)]" />
            <h3 className="font-semibold text-[var(--ral-white)]">Recent Trace Logs</h3>
          </div>
          <span className="text-[var(--ral-grey-mid)] text-xs">Live · 30s</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] bg-[var(--bg-element)]">
                {['Time', 'Model', 'Tokens', 'Status', 'Cost', 'Action'].map(h => (
                  <th key={h} className="py-3 px-4 text-[10px] font-bold uppercase tracking-wider text-[var(--ral-grey-mid)]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recentLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-xs text-[var(--ral-grey-mid)]">No requests yet</td>
                </tr>
              ) : (
                recentLogs.map((log) => (
                  <tr key={log.id} className="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-hover)]">
                    <td className="py-3 px-4 font-mono text-xs text-[var(--ral-grey-light)]">{log.started_at?.slice(11, 19)}</td>
                    <td className="py-3 px-4 text-xs text-[var(--ral-white)] truncate max-w-[120px]">{log.model}</td>
                    <td className="py-3 px-4 font-mono text-xs text-[var(--ral-grey-light)]">{log.total_tokens?.toLocaleString()}</td>
                    <td className="py-3 px-4"><Badge status={log.status_code === 200 ? '200' : log.status_code === 429 ? '429' : 'error'} /></td>
                    <td className="py-3 px-4 font-mono text-xs text-[var(--ral-rust-bright)]">${(log.cost_usd || 0).toFixed(5)}</td>
                    <td className="py-3 px-4">
                      <button onClick={() => onViewPrompt(log)} className="p-1.5 text-[var(--ral-grey-mid)] hover:text-[var(--ral-rust-bright)]">
                        <Eye size={16} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default OverviewView;
