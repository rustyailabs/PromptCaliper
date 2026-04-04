import { AlertTriangle } from 'lucide-react';

export default function ConfirmDialog({ title, message, confirmLabel = 'Confirm', onConfirm, onCancel, danger = false }) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="glass-panel rounded-xl p-6 w-full max-w-md mx-4 shadow-xl">
        <div className="flex items-center gap-3 mb-4">
          {danger && <AlertTriangle size={20} className="text-[var(--ral-rust-bright)]" />}
          <h3 className="text-[var(--ral-white)] font-semibold text-lg">{title}</h3>
        </div>
        <p className="text-[var(--ral-grey-light)] text-sm mb-6">{message}</p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg border border-[var(--ral-border)] text-[var(--ral-grey-light)] hover:text-[var(--ral-white)] text-sm transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              danger
                ? 'bg-red-700 hover:bg-red-600 text-white'
                : 'bg-[var(--ral-rust-core)] hover:bg-[var(--ral-rust-bright)] text-white'
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
