import React from 'react';

const Badge = ({ status }) => {
    if (status === 200 || status === 'active') return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[rgba(0,212,255,0.1)] text-[var(--ral-cyan)] border border-[rgba(0,212,255,0.2)] uppercase">
            {status === 200 ? '200 OK' : status}
        </span>
    );
    if (status === 429 || status === 'inactive') return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[rgba(192,83,26,0.1)] text-[var(--ral-rust-core)] border border-[rgba(192,83,26,0.2)] uppercase">
            {status === 429 ? '429 LMT' : status}
        </span>
    );
    if (status === 'maintenance') return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[rgba(255,255,0,0.1)] text-[#FFC107] border border-[rgba(255,255,0,0.2)] uppercase">
            MAINT
        </span>
    );
    return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[var(--bg-element)] text-[var(--ral-grey-light)] border border-[var(--border-element)] uppercase">
            {status}
        </span>
    );
};

export default Badge;
