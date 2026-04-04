import { useState } from 'react';
import { Cpu, Eye, EyeOff, Lock, User } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

export default function LoginView() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!username || !password) return;
    setLoading(true);
    setError('');
    try {
      await login(username, password);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--ral-black)] relative overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(192,83,26,0.15)_0%,_transparent_60%)] pointer-events-none" />

      <div className="w-full max-w-sm mx-4 z-10">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-full border-2 border-[var(--ral-rust-core)] flex items-center justify-center shadow-[0_0_20px_rgba(192,83,26,0.5)]">
            <Cpu size={20} className="text-[var(--ral-rust-bright)]" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[var(--ral-white)] tracking-wide">
              PROMPT<span className="text-[var(--ral-rust-core)]">CALIPER</span>
            </h1>
            <p className="text-[10px] text-[var(--ral-grey-mid)] uppercase tracking-[0.2em]">AI Gateway</p>
          </div>
        </div>

        {/* Card */}
        <div className="glass-panel rounded-xl p-8 shadow-2xl">
          <h2 className="text-lg font-semibold text-[var(--ral-white)] mb-1">Sign in</h2>
          <p className="text-sm text-[var(--ral-grey-mid)] mb-6">Admin console access</p>

          {error && (
            <div className="mb-4 p-3 rounded-lg border alert-red text-danger text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[var(--ral-grey-light)] uppercase tracking-wider mb-1.5">
                Username
              </label>
              <div className="relative">
                <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ral-grey-mid)]" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin"
                  autoComplete="username"
                  className="w-full bg-[var(--bg-element)] border border-[var(--border-element)] rounded-lg pl-9 pr-4 py-2.5 text-sm text-[var(--ral-white)] placeholder-[var(--ral-grey-mid)] focus:outline-none focus:border-[var(--ral-rust-core)] focus:ring-1 focus:ring-[var(--ral-rust-core)] transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--ral-grey-light)] uppercase tracking-wider mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ral-grey-mid)]" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  className="w-full bg-[var(--bg-element)] border border-[var(--border-element)] rounded-lg pl-9 pr-10 py-2.5 text-sm text-[var(--ral-white)] placeholder-[var(--ral-grey-mid)] focus:outline-none focus:border-[var(--ral-rust-core)] focus:ring-1 focus:ring-[var(--ral-rust-core)] transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--ral-grey-mid)] hover:text-[var(--ral-white)]"
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full py-2.5 rounded-lg bg-[var(--ral-rust-core)] hover:bg-[var(--ral-rust-bright)] disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold transition-colors shadow-[0_0_16px_rgba(192,83,26,0.4)] mt-2"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-[var(--ral-grey-mid)] mt-6">
          PromptCaliper AI Gateway v1.0 —{' '}
          <a href="https://www.rustyailabs.com/" target="_blank" rel="noopener noreferrer" className="text-[var(--ral-rust-bright)] hover:text-[var(--ral-rust-glow)] underline underline-offset-2 transition-colors">
            Rusty AI Labs
          </a>
        </p>
      </div>
    </div>
  );
}
