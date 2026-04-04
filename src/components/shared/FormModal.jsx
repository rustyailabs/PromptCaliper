import { X } from 'lucide-react';

export default function FormModal({ title, onClose, children, maxWidth = 'max-w-lg' }) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className={`glass-panel rounded-xl w-full ${maxWidth} shadow-xl max-h-[90vh] flex flex-col`}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--ral-border)]">
          <h3 className="text-[var(--ral-white)] font-semibold">{title}</h3>
          <button onClick={onClose} className="text-[var(--ral-grey-mid)] hover:text-[var(--ral-white)] transition-colors">
            <X size={18} />
          </button>
        </div>
        {/* Body */}
        <div className="overflow-y-auto flex-1 px-6 py-4">
          {children}
        </div>
      </div>
    </div>
  );
}

// Reusable form field components used inside FormModal
export function Field({ label, children, hint }) {
  return (
    <div className="mb-4">
      <label className="block text-xs font-medium text-[var(--ral-grey-light)] uppercase tracking-wider mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-xs text-[var(--ral-grey-mid)] mt-1">{hint}</p>}
    </div>
  );
}

export function Input({ className = '', ...props }) {
  return (
    <input
      className={`w-full bg-[var(--bg-element)] border border-[var(--border-element)] rounded-lg px-3 py-2 text-sm text-[var(--ral-white)] focus:outline-none focus:border-[var(--ral-rust-core)] focus:ring-1 focus:ring-[var(--ral-rust-core)] transition-colors ${className}`}
      {...props}
    />
  );
}

export function Select({ className = '', children, ...props }) {
  return (
    <select
      className={`w-full bg-[var(--bg-element)] border border-[var(--border-element)] rounded-lg px-3 py-2 text-sm text-[var(--ral-white)] focus:outline-none focus:border-[var(--ral-rust-core)] transition-colors ${className}`}
      {...props}
    >
      {children}
    </select>
  );
}

export function FormActions({ onCancel, submitLabel = 'Save', loading = false }) {
  return (
    <div className="flex gap-3 justify-end pt-4 border-t border-[var(--ral-border)] mt-4">
      <button
        type="button"
        onClick={onCancel}
        className="px-4 py-2 rounded-lg border border-[var(--ral-border)] text-[var(--ral-grey-light)] hover:text-[var(--ral-white)] text-sm transition-colors"
      >
        Cancel
      </button>
      <button
        type="submit"
        disabled={loading}
        className="px-4 py-2 rounded-lg bg-[var(--ral-rust-core)] hover:bg-[var(--ral-rust-bright)] disabled:opacity-50 text-white text-sm font-medium transition-colors"
      >
        {loading ? 'Saving…' : submitLabel}
      </button>
    </div>
  );
}
