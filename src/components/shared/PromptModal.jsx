import React from 'react';
import { Terminal, X } from 'lucide-react';

const PromptModal = ({ log, onClose }) => {
    if (!log) return null;

    // Format prompt_messages array into readable text
    const promptText = Array.isArray(log.prompt_messages)
        ? log.prompt_messages.map(m => `[${m.role}]: ${m.content}`).join('\n\n')
        : (log.prompt_messages || '');

    const responseText = log.response_content || (log.status_code !== 200 ? `Blocked — HTTP ${log.status_code}` : '(no response)');
    const latency = log.latency_ms != null ? `${log.latency_ms} ms` : '—';
    const tokens = log.total_tokens ?? '—';
    const cost = log.cost_usd != null ? `$${Number(log.cost_usd).toFixed(5)}` : '—';

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <div className="glass-panel w-full max-w-3xl rounded-lg shadow-2xl border border-[var(--ral-rust-core)] flex flex-col max-h-[90vh]">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-[var(--ral-border)] bg-[var(--bg-element)]">
                    <div className="flex items-center gap-3">
                        <Terminal size={20} className="text-[var(--ral-rust-core)]" />
                        <h3 className="text-lg font-bold text-[var(--ral-white)]">Request Inspection</h3>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[var(--bg-hover)] text-[var(--ral-grey-light)]">
                            ID: {log.id}
                        </span>
                    </div>
                    <button onClick={onClose} className="text-[var(--ral-grey-light)] hover:text-[var(--ral-white)]">
                        <X size={24} />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto space-y-6">
                    {/* Metadata Grid */}
                    <div className="grid grid-cols-4 gap-4 p-4 rounded bg-[var(--bg-element)] border border-[var(--ral-border)]">
                        <div>
                            <div className="text-[10px] uppercase tracking-wider text-[var(--ral-grey-mid)] mb-1">Model</div>
                            <div className="text-sm text-[var(--ral-cyan)] font-mono">{log.model}</div>
                        </div>
                        <div>
                            <div className="text-[10px] uppercase tracking-wider text-[var(--ral-grey-mid)] mb-1">Latency</div>
                            <div className="text-sm text-[var(--ral-white)] font-mono">{latency}</div>
                        </div>
                        <div>
                            <div className="text-[10px] uppercase tracking-wider text-[var(--ral-grey-mid)] mb-1">Tokens</div>
                            <div className="text-sm text-[var(--ral-white)] font-mono">{tokens}</div>
                        </div>
                        <div>
                            <div className="text-[10px] uppercase tracking-wider text-[var(--ral-grey-mid)] mb-1">Cost</div>
                            <div className="text-sm text-[var(--ral-rust-bright)] font-mono">{cost}</div>
                        </div>
                    </div>

                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <h4 className="text-sm font-semibold text-[var(--ral-grey-light)] uppercase tracking-wide">Input Prompt</h4>
                            <span className="text-[10px] font-mono text-[var(--ral-grey-mid)]">Token Count: {log.prompt_tokens ?? '—'}</span>
                        </div>
                        <div className="w-full p-4 rounded bg-[var(--bg-terminal)] border border-[var(--ral-grey-mid)] font-mono text-sm text-[var(--ral-grey-light)] whitespace-pre-wrap">
                            {promptText || '(empty)'}
                        </div>
                    </div>

                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <h4 className="text-sm font-semibold text-[var(--ral-grey-light)] uppercase tracking-wide">Model Response</h4>
                            <span className="text-[10px] font-mono text-[var(--ral-grey-mid)]">Token Count: {log.completion_tokens ?? '—'}</span>
                        </div>
                        <div className="w-full p-4 rounded bg-[var(--bg-terminal)] border border-[rgba(0,212,255,0.2)] font-mono text-sm text-[var(--ral-cyan-dim)] whitespace-pre-wrap">
                            {responseText}
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-[var(--ral-border)] bg-[var(--bg-element)] flex justify-end gap-3">
                    <button onClick={onClose} className="px-4 py-2 rounded text-sm text-[var(--ral-grey-light)] hover:text-white transition-colors">Close</button>
                    <button className="px-4 py-2 rounded bg-[var(--ral-rust-core)] text-white text-sm font-medium hover:bg-[var(--ral-rust-bright)] transition-colors shadow-[0_0_15px_rgba(192,83,26,0.4)]">
                        Replay Request
                    </button>
                </div>
            </div>
        </div>
    );
};

export default PromptModal;
