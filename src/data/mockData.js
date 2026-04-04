import { 
  Activity, 
  Clock, 
  DollarSign, 
  ShieldAlert, 
} from 'lucide-react';

export const MOCK_STATS = [
  { label: 'Total Requests', value: '2.4M', trend: '+12%', icon: Activity, color: 'var(--ral-cyan)' },
  { label: 'Avg Latency', value: '480ms', trend: '-8%', icon: Clock, color: 'var(--ral-rust-bright)' },
  { label: 'Total Cost (Est)', value: '$4,290', trend: '+5%', icon: DollarSign, color: 'var(--ral-white)' },
  { label: 'Blocked (Rate Limit)', value: '142', trend: '+2%', icon: ShieldAlert, color: 'var(--ral-rust-core)' },
];

export const USAGE_DATA = [
  { time: '00:00', requests: 400, cost: 24 },
  { time: '04:00', requests: 300, cost: 18 },
  { time: '08:00', requests: 1200, cost: 85 },
  { time: '12:00', requests: 2800, cost: 150 },
  { time: '16:00', requests: 2400, cost: 130 },
  { time: '20:00', requests: 1800, cost: 90 },
  { time: '23:59', requests: 900, cost: 45 },
];

export const ORG_COST_HISTORY = [
  { month: 'Jan', Marketing: 400, Engineering: 2400, Ops: 200, DataScience: 800 },
  { month: 'Feb', Marketing: 300, Engineering: 1398, Ops: 250, DataScience: 1200 },
  { month: 'Mar', Marketing: 500, Engineering: 3800, Ops: 300, DataScience: 1100 },
  { month: 'Apr', Marketing: 200, Engineering: 3908, Ops: 280, DataScience: 1300 },
  { month: 'May', Marketing: 600, Engineering: 4800, Ops: 350, DataScience: 1400 },
  { month: 'Jun', Marketing: 700, Engineering: 5300, Ops: 400, DataScience: 1700 },
];

export const TOKEN_SPLIT_DATA = [
  { day: 'Mon', input: 450000, output: 120000 },
  { day: 'Tue', input: 520000, output: 140000 },
  { day: 'Wed', input: 480000, output: 130000 },
  { day: 'Thu', input: 610000, output: 180000 },
  { day: 'Fri', input: 550000, output: 160000 },
  { day: 'Sat', input: 220000, output: 50000 },
  { day: 'Sun', input: 180000, output: 40000 },
];

export const ANALYTICS_PIE_DATA = [
  { name: 'Marketing', value: 400, color: 'var(--ral-rust-core)' },
  { name: 'Engineering', value: 300, color: 'var(--ral-cyan)' },
  { name: 'Data Science', value: 300, color: 'var(--ral-rust-deep)' },
  { name: 'Operations', value: 200, color: 'var(--ral-grey-light)' },
];

export const REQUEST_LOGS = [
  { id: 'req_8f92a', timestamp: '10:42:05', user: 'eng-team-alpha', model: 'gpt-4-turbo', tokens: 420, cost: '$0.012', latency: '890ms', status: 200, prompt: "Refactor this React component to use hooks...", response: "Here is the refactored component..." },
  { id: 'req_8f92b', timestamp: '10:42:08', user: 'data-science-01', model: 'claude-3-opus', tokens: 1540, cost: '$0.045', latency: '2.1s', status: 200, prompt: "Analyze the attached CSV dataset for trends...", response: "Based on the analysis..." },
  { id: 'req_8f92c', timestamp: '10:42:15', user: 'intern-bot-test', model: 'llama-3-70b', tokens: 0, cost: '$0.000', latency: '45ms', status: 429, prompt: "Generate 500 variations of...", response: "Rate limit exceeded. Quota: 100 RPM." },
  { id: 'req_8f92d', timestamp: '10:42:22', user: 'marketing-copy', model: 'gpt-3.5-turbo', tokens: 120, cost: '$0.002', latency: '320ms', status: 200, prompt: "Write a tagline for Rusty AI Labs...", response: "Fight Rust, Restore Trust." },
  { id: 'req_8f92e', timestamp: '10:42:45', user: 'eng-team-beta', model: 'gemini-1.5-pro', tokens: 8500, cost: '$0.021', latency: '3.4s', status: 200, prompt: "Summarize this 50 page technical manual...", response: "Here is the summary..." },
];

export const POLICIES = [
  { id: 1, name: "Global Hard Cap", scope: "Global", type: "Cost", limit: "$5,000 / mo", status: "active", usage: 85 },
  { id: 2, name: "Eng Team Tier", scope: "Group: Engineering", type: "RPM", limit: "500 RPM", status: "active", usage: 42 },
  { id: 3, name: "Intern Sandbox", scope: "Group: Interns", type: "Model Restricted", limit: "No GPT-4", status: "active", usage: 12 },
  { id: 4, name: "Weekend Throttle", scope: "Global", type: "Latency", limit: "+200ms delay", status: "inactive", usage: 0 },
];

export const USERS_LIST = [
  { id: 'u_1', name: 'Alice Chen', role: 'Admin', team: 'Engineering', key: 'sk-rail...9f2a', spend: '$1,204', status: 'active' },
  { id: 'u_2', name: 'Bob Smith', role: 'Editor', team: 'Marketing', key: 'sk-rail...8b11', spend: '$340', status: 'active' },
  { id: 'u_3', name: 'Service Bot 01', role: 'Bot', team: 'Ops', key: 'sk-rail...22cc', spend: '$890', status: 'active' },
  { id: 'u_4', name: 'Dave Wilson', role: 'Viewer', team: 'Sales', key: 'sk-rail...00aa', spend: '$45', status: 'inactive' },
];

export const MODELS_CONFIG = [
  { id: 'm_1', name: 'GPT-4 Turbo', provider: 'OpenAI', type: 'Chat', context: '128k', costIn: '$10.00', costOut: '$30.00', status: 'active', latency: 450 },
  { id: 'm_2', name: 'Claude 3 Opus', provider: 'Anthropic', type: 'Chat', context: '200k', costIn: '$15.00', costOut: '$75.00', status: 'active', latency: 980 },
  { id: 'm_3', name: 'Gemini 1.5 Pro', provider: 'Google', type: 'Chat', context: '1M', costIn: '$3.50', costOut: '$10.50', status: 'maintenance', latency: 620 },
  { id: 'm_4', name: 'Llama 3 70B', provider: 'Groq', type: 'Chat', context: '8k', costIn: '$0.70', costOut: '$0.90', status: 'active', latency: 120 },
];
