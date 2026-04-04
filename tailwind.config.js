/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                background: 'var(--color-bg)',
                surface: 'var(--color-surface)',
                primary: 'var(--color-primary)',
                'primary-foreground': 'var(--color-primary-foreground)',
                text: {
                    DEFAULT: 'var(--color-text)',
                    muted: 'var(--color-text-muted)',
                },
                border: 'var(--color-border)',
            },
        },
    },
    plugins: [],
}
