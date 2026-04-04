export default function LoadingSpinner({ size = 'md', className = '' }) {
  const sizeClass = size === 'sm' ? 'w-4 h-4' : size === 'lg' ? 'w-10 h-10' : 'w-6 h-6';
  return (
    <div className={`${sizeClass} border-2 border-[var(--ral-grey-mid)] border-t-[var(--ral-rust-bright)] rounded-full animate-spin ${className}`} />
  );
}
