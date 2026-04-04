import { DollarSign, Database, Zap } from 'lucide-react';
import { useEffect } from 'react';
import {
  BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, Legend, PieChart, Pie, Cell
} from 'recharts';
import LoadingSpinner from '../shared/LoadingSpinner';
import { usePolling } from '../../hooks/usePolling';
import { analyticsService } from '../../services/analyticsService';

const COLORS = ['var(--ral-rust-core)', 'var(--ral-cyan)', 'var(--ral-rust-bright)', 'var(--ral-grey-light)'];

const AnalyticsView = ({ timeRange = '24h' }) => {
  const { data: overview, error: overviewError, refresh: refreshOverview } =
    usePolling(() => analyticsService.getOverview(timeRange), 30000);
  const { data: teamHistory, isLoading: loadingTeam, error: teamError } =
    usePolling(() => analyticsService.getTeamSpendHistory(6), 30000);
  const { data: tokenData, isLoading: loadingTokens, error: tokenError } =
    usePolling(() => analyticsService.getTokenEconomics(7), 30000);
  const { data: modelDist, isLoading: loadingPie, error: modelError, refresh: refreshModel } =
    usePolling(() => analyticsService.getModelDistribution(timeRange), 30000);

  // Re-fetch time-range-sensitive charts immediately when the prop changes
  // instead of waiting for the next 30-second polling interval.
  useEffect(() => {
    refreshOverview();
    refreshModel();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeRange]);

  // Derive team names from pivot data
  const teamNames = teamHistory
    ? [...new Set(teamHistory.flatMap(r => Object.keys(r).filter(k => k !== 'month')))]
    : [];

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
    </div>
  );
};

export default AnalyticsView;
