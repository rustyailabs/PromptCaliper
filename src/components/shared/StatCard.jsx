import React from 'react';

const StatCard = ({ label, value, trend, icon: Icon, color }) => (
    <div className="glass-panel p-6 rounded-lg relative overflow-hidden group hover:border-[var(--ral-rust-core)] transition-colors">
        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <Icon size={64} color={color} />
        </div>
        <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-full bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.05)]">
                <Icon size={18} color={color} />
            </div>
            <span className="text-[var(--ral-grey-light)] text-xs uppercase tracking-wider font-semibold">{label}</span>
        </div>
        <div className="flex items-end gap-3 mt-2">
            <span className="text-3xl font-bold text-[var(--ral-white)]">{value}</span>
            <span className={`text-xs font-mono mb-1 ${trend.startsWith('+') ? 'text-[var(--ral-cyan)]' : 'text-[var(--ral-rust-bright)]'}`}>
                {trend}
            </span>
        </div>
    </div>
);

export default StatCard;
