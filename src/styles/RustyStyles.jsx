const RustyStyles = () => (
  <style>{`
    :root {
      /* ── Brand Colors (Constant) ── */
      --ral-rust-deep:    #7A2F08;
      --ral-rust-core:    #C0531A;
      --ral-rust-glow:    #FF9356;

      --ral-font-mono: 'JetBrains Mono', 'Fira Code', monospace;
      --ral-border:       rgba(192, 83, 26, 0.30);
      --ral-border-hover: rgba(192, 83, 26, 0.60);
    }

    /* ── Dark Theme (Default/Rusty) ── */
    :root, :root.dark {
      --ral-black:        #080808;
      --ral-grey-dark:    #1E1B18;
      --ral-grey-mid:     #7A746E;  /* Warm grey — readable on dark surfaces */
      --ral-grey-light:   #B0ABA4;
      --ral-white:        #F0ECE6;

      /* Accent colors — theme-aware */
      --ral-rust-bright:  #E07B3C;
      --ral-cyan:         #00D4FF;
      --ral-cyan-dim:     #0099BB;

      --bg-overlay:       rgba(30, 27, 24, 0.7);

      /* Utility Colors - Dark */
      --bg-element:       rgba(255, 255, 255, 0.03);
      --bg-hover:         rgba(255, 255, 255, 0.05);
      --border-element:   rgba(255, 255, 255, 0.1);
      --border-subtle:    rgba(255, 255, 255, 0.05);
      --bg-terminal:      #050505;
    }

    /* ── Light Theme ── */
    :root.light {
      --ral-black:        #F0F4F8;  /* Page background */
      --ral-grey-dark:    #FFFFFF;  /* Surface / sidebar */
      --ral-grey-mid:     #64748B;  /* Slate-500 — ~4.6:1 on white, meets WCAG AA */
      --ral-grey-light:   #334155;  /* Slate-700 — strong secondary text */
      --ral-white:        #0F172A;  /* Slate-900 — primary text */

      /* Accent colors re-mapped for light backgrounds */
      --ral-rust-bright:  #9A3412;  /* Orange-800 — ~7.5:1 on white */
      --ral-cyan:         #0369A1;  /* Sky-700 — ~5.9:1 on white */
      --ral-cyan-dim:     #075985;  /* Sky-800 */

      --bg-overlay:       rgba(255, 255, 255, 0.9);
      --ral-border:       rgba(192, 83, 26, 0.20);

      /* Utility Colors - Light */
      --bg-element:       rgba(0, 0, 0, 0.04);
      --bg-hover:         rgba(0, 0, 0, 0.06);
      --border-element:   rgba(0, 0, 0, 0.12);
      --border-subtle:    rgba(0, 0, 0, 0.08);
      --bg-terminal:      #F1F5F9;  /* Slate-100 for code blocks */
    }

    body {
      background-color: var(--ral-black);
      color: var(--ral-white);
      font-family: 'Inter', sans-serif;
      transition: background-color 0.3s ease, color 0.3s ease;
    }

    .glass-panel {
      background: var(--bg-overlay);
      backdrop-filter: blur(12px);
      border: 1px solid var(--ral-border);
    }
    
    .glass-panel-hover:hover {
       border-color: var(--ral-rust-core);
       box-shadow: 0 0 15px rgba(192, 83, 26, 0.15);
    }

    /* Scrollbar */
    ::-webkit-scrollbar {
      width: 8px;
      height: 8px;
    }
    ::-webkit-scrollbar-track {
      background: var(--ral-black); 
    }
    ::-webkit-scrollbar-thumb {
      background: var(--ral-grey-mid); 
      border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: var(--ral-rust-core); 
    }
    
    /* ── Dropdown / Select ── */
    select {
      background-color: var(--ral-grey-dark);
      color: var(--ral-white);
      color-scheme: dark;
    }

    select option {
      background-color: var(--ral-grey-dark);
      color: var(--ral-white);
    }

    select option:hover,
    select option:checked {
      background-color: var(--ral-rust-core);
      color: var(--ral-white);
    }

    :root.light select {
      color-scheme: light;
    }

    /* ── Semantic badge classes (dark default) ── */
    .badge-red    { background: rgba(153,27,27,0.25);  color: #FCA5A5; }
    .badge-orange { background: rgba(154,52,18,0.25);  color: #FDBA74; }
    .badge-yellow { background: rgba(113,63,18,0.25);  color: #FDE047; }
    .badge-green  { background: rgba(20,83,45,0.25);   color: #86EFAC; }
    .badge-blue   { background: rgba(30,58,138,0.25);  color: #93C5FD; }
    .badge-purple { background: rgba(88,28,135,0.25);  color: #D8B4FE; }
    .badge-cyan   { background: rgba(8,145,178,0.25);  color: var(--ral-cyan); }

    :root.light .badge-red    { background: #FEE2E2; color: #991B1B; }
    :root.light .badge-orange { background: #FFEDD5; color: #9A3412; }
    :root.light .badge-yellow { background: #FEF9C3; color: #713F12; }
    :root.light .badge-green  { background: #DCFCE7; color: #14532D; }
    :root.light .badge-blue   { background: #DBEAFE; color: #1E40AF; }
    :root.light .badge-purple { background: #F3E8FF; color: #6B21A8; }
    :root.light .badge-cyan   { background: #E0F2FE; color: #0369A1; }

    /* ── Semantic alert panels ── */
    .alert-red   { background: rgba(153,27,27,0.15);  border-color: rgba(239,68,68,0.4); }
    .alert-green { background: rgba(20,83,45,0.15);   border-color: rgba(74,222,128,0.4); }

    :root.light .alert-red   { background: #FEF2F2; border-color: #FECACA; }
    :root.light .alert-green { background: #F0FDF4; border-color: #BBF7D0; }

    /* ── Semantic status text ── */
    .text-danger  { color: #FCA5A5; }
    .text-success { color: #86EFAC; }
    .icon-danger  { color: #F87171; }
    .icon-success { color: #4ADE80; }

    :root.light .text-danger  { color: #991B1B; }
    :root.light .text-success { color: #14532D; }
    :root.light .icon-danger  { color: #DC2626; }
    :root.light .icon-success { color: #16A34A; }

    /* ── Hover danger (delete buttons) ── */
    .hover-danger:hover { color: #F87171; }
    :root.light .hover-danger:hover { color: #DC2626; }

    .toggle-switch {
      transition: all 0.3s ease;
    }

    .fade-enter {
      opacity: 0;
      transform: translateY(-10px);
    }
    .fade-enter-active {
      opacity: 1;
      transform: translateY(0);
      transition: opacity 300ms, transform 300ms;
    }
  `}</style>
);

export default RustyStyles;
