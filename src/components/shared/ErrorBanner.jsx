import { AlertTriangle, X } from 'lucide-react';
import { useState } from 'react';

export default function ErrorBanner({ message, onDismiss }) {
  const [visible, setVisible] = useState(true);
  if (!message || !visible) return null;

  const dismiss = () => {
    setVisible(false);
    onDismiss?.();
  };

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-red-900/30 border border-red-500/40 text-red-300 text-sm mb-4">
      <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
      <span className="flex-1">{message}</span>
      <button onClick={dismiss} className="text-red-400 hover:text-red-200">
        <X size={14} />
      </button>
    </div>
  );
}
