import { useState } from 'react';
import {
  Activity,
  Database,
  BarChart3,
  ShieldAlert,
  Users,
  Zap,
  Cpu,
  Search,
  Key,
  DollarSign,
  Shield,
  HardDrive,
  Bell,
  LogOut,
} from 'lucide-react';
import RustyStyles from './styles/RustyStyles';
import SidebarItem from './components/shared/SidebarItem';
import OverviewView from './components/views/OverviewView';
import LogsView from './components/views/LogsView';
import AnalyticsView from './components/views/AnalyticsView';
import RateLimitingView from './components/views/RateLimitingView';
import UsersView from './components/views/UsersView';
import ModelConfigView from './components/views/ModelConfigView';
import VirtualKeysView from './components/views/VirtualKeysView';
import BudgetSpendView from './components/views/BudgetSpendView';
import GuardrailsView from './components/views/GuardrailsView';
import CacheView from './components/views/CacheView';
import AlertsView from './components/views/AlertsView';
import PromptModal from './components/shared/PromptModal';
import ThemeToggle from './components/ThemeToggle';
import LoginView from './components/views/LoginView';
import LoadingSpinner from './components/shared/LoadingSpinner';
import { useAuth } from './hooks/useAuth';

const VIEW_TITLES = {
  overview:   'Overview',
  logs:       'Request Logs',
  analytics:  'Analytics',
  limits:     'Rate Limiting',
  users:      'Users',
  models:     'Model Registry',
  virtualkeys:'Virtual Keys',
  budgets:    'Budget & Spend',
  guardrails: 'Guardrails',
  cache:      'Cache',
  alerts:     'Alerts',
};

// Only these views consume the time-range filter — hide it everywhere else
const TIME_RANGE_VIEWS = new Set(['overview', 'analytics']);

export default function App() {
  const { isAuthenticated, isLoading, user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedLog, setSelectedLog] = useState(null);
  const [timeRange, setTimeRange] = useState('24h');

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--ral-black)]">
        <RustyStyles />
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <>
        <RustyStyles />
        <LoginView />
      </>
    );
  }

  const initials = user?.username?.slice(0, 2).toUpperCase() || 'AD';

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[var(--ral-black)] selection:bg-[var(--ral-rust-core)] selection:text-white">
      <RustyStyles />

      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 border-r border-[var(--ral-border)] bg-[var(--ral-grey-dark)] flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-[var(--border-subtle)]">
          <div className="w-8 h-8 rounded-full border-2 border-[var(--ral-rust-core)] flex items-center justify-center mr-3 shadow-[0_0_10px_rgba(192,83,26,0.4)]">
            <Cpu size={16} className="text-[var(--ral-rust-core)]" />
          </div>
          <div>
            <h1 className="font-bold text-[var(--ral-white)] tracking-wide">PROMPT<span className="text-[var(--ral-rust-core)]">CALIPER</span></h1>
            <p className="text-[9px] text-[var(--ral-grey-mid)] uppercase tracking-[0.2em]">AI Gateway</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-4 space-y-0.5 overflow-y-auto">
          <div className="text-[10px] font-bold text-[var(--ral-grey-mid)] uppercase tracking-wider px-4 mb-2 mt-2">Observability</div>
          <SidebarItem icon={Activity} label="Overview" active={activeTab === 'overview'} onClick={() => setActiveTab('overview')} />
          <SidebarItem icon={Database} label="Request Logs" active={activeTab === 'logs'} onClick={() => setActiveTab('logs')} />
          <SidebarItem icon={BarChart3} label="Analytics" active={activeTab === 'analytics'} onClick={() => setActiveTab('analytics')} />

          <div className="text-[10px] font-bold text-[var(--ral-grey-mid)] uppercase tracking-wider px-4 mb-2 mt-6">Gateway</div>
          <SidebarItem icon={Key} label="Virtual Keys" active={activeTab === 'virtualkeys'} onClick={() => setActiveTab('virtualkeys')} />
          <SidebarItem icon={DollarSign} label="Budget & Spend" active={activeTab === 'budgets'} onClick={() => setActiveTab('budgets')} />
          <SidebarItem icon={Zap} label="Model Registry" active={activeTab === 'models'} onClick={() => setActiveTab('models')} />
          <SidebarItem icon={ShieldAlert} label="Rate Limiting" active={activeTab === 'limits'} onClick={() => setActiveTab('limits')} />

          <div className="text-[10px] font-bold text-[var(--ral-grey-mid)] uppercase tracking-wider px-4 mb-2 mt-6">Safety</div>
          <SidebarItem icon={Shield} label="Guardrails" active={activeTab === 'guardrails'} onClick={() => setActiveTab('guardrails')} />
          <SidebarItem icon={HardDrive} label="Cache" active={activeTab === 'cache'} onClick={() => setActiveTab('cache')} />
          <SidebarItem icon={Bell} label="Alerts" active={activeTab === 'alerts'} onClick={() => setActiveTab('alerts')} />

          <div className="text-[10px] font-bold text-[var(--ral-grey-mid)] uppercase tracking-wider px-4 mb-2 mt-6">Admin</div>
          <SidebarItem icon={Users} label="Users" active={activeTab === 'users'} onClick={() => setActiveTab('users')} />
        </nav>

        {/* User Footer */}
        <div className="p-4 border-t border-[var(--border-subtle)]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-[var(--ral-rust-deep)] flex items-center justify-center text-xs font-bold text-[var(--ral-rust-bright)]">
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-[var(--ral-white)] truncate">{user?.username}</div>
              <div className="text-[10px] text-[var(--ral-grey-light)]">{user?.is_superadmin ? 'Superadmin' : 'Admin'}</div>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              className="text-[var(--ral-grey-mid)] hover:text-[var(--ral-rust-bright)] transition-colors"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        <div className="absolute top-0 left-0 w-full h-[500px] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-[rgba(192,83,26,0.15)] via-transparent to-transparent pointer-events-none" />

        {/* Header */}
        <header className="h-16 flex items-center justify-between px-8 border-b border-[var(--border-subtle)] bg-[var(--bg-overlay)] backdrop-blur z-10">
          <h2 className="text-lg font-medium text-[var(--ral-white)]">
            {VIEW_TITLES[activeTab] || activeTab}
          </h2>

          <div className="flex items-center gap-4">
            <div className="relative group">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ral-grey-mid)] group-focus-within:text-[var(--ral-rust-bright)] transition-colors" size={16} />
              <input
                type="text"
                placeholder="Search trace ID, user..."
                className="bg-[var(--bg-element)] border border-[var(--border-element)] rounded-full py-1.5 pl-10 pr-4 text-sm text-[var(--ral-white)] focus:outline-none focus:border-[var(--ral-rust-core)] focus:ring-1 focus:ring-[var(--ral-rust-core)] w-64 transition-all"
              />
            </div>

            {TIME_RANGE_VIEWS.has(activeTab) && (
              <div className="flex bg-[var(--bg-element)] rounded-md p-1 border border-[var(--border-element)]">
                {['1h', '24h', '7d'].map((t) => (
                  <button
                    key={t}
                    onClick={() => setTimeRange(t)}
                    className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
                      timeRange === t ? 'bg-[var(--ral-grey-mid)] text-white shadow-sm' : 'text-[var(--ral-grey-light)] hover:text-white'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            )}

            <ThemeToggle />
          </div>
        </header>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-8 z-0">
          {activeTab === 'overview'    && <OverviewView onViewPrompt={setSelectedLog} timeRange={timeRange} />}
          {activeTab === 'logs'        && <LogsView onViewPrompt={setSelectedLog} />}
          {activeTab === 'analytics'   && <AnalyticsView timeRange={timeRange} />}
          {activeTab === 'limits'      && <RateLimitingView />}
          {activeTab === 'users'       && <UsersView />}
          {activeTab === 'models'      && <ModelConfigView />}
          {activeTab === 'virtualkeys' && <VirtualKeysView />}
          {activeTab === 'budgets'     && <BudgetSpendView timeRange={timeRange} />}
          {activeTab === 'guardrails'  && <GuardrailsView />}
          {activeTab === 'cache'       && <CacheView />}
          {activeTab === 'alerts'      && <AlertsView />}

          <div className="mt-8 text-center text-xs text-[var(--ral-grey-mid)] pb-4">
            PromptCaliper AI Gateway v1.0 — Engineered by{' '}
            <a href="https://www.rustyailabs.com/" target="_blank" rel="noopener noreferrer" className="text-[var(--ral-rust-bright)] hover:text-[var(--ral-rust-glow)] underline underline-offset-2 transition-colors">
              Rusty AI Labs
            </a>
          </div>
        </div>
      </main>

      {selectedLog && <PromptModal log={selectedLog} onClose={() => setSelectedLog(null)} />}
    </div>
  );
}
