import React from 'react';

const SidebarItem = ({ icon: Icon, label, active, onClick }) => (
    <button
        onClick={onClick}
        className={`w-full flex items-center gap-3 px-4 py-3 rounded-md transition-all duration-300 group
      ${active
                ? 'bg-[rgba(192,83,26,0.1)] border-r-2 border-[var(--ral-rust-core)] text-[var(--ral-white)]'
                : 'text-[var(--ral-grey-light)] hover:bg-[rgba(255,255,255,0.03)] hover:text-[var(--ral-rust-bright)]'
            }`}
    >
        <Icon size={18} className={`${active ? 'text-[var(--ral-rust-core)]' : 'text-[var(--ral-grey-mid)] group-hover:text-[var(--ral-rust-bright)]'}`} />
        <span className="font-medium text-sm tracking-wide">{label}</span>
    </button>
);

export default SidebarItem;
