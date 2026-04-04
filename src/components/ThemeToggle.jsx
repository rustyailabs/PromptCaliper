import { useTheme } from '../context/ThemeContext';
import { Moon, Sun } from 'lucide-react';

const ThemeToggle = () => {
    const { theme, toggleTheme } = useTheme();

    return (
        <button
            onClick={toggleTheme}
            className="p-2 rounded-full hover:bg-surface border border-border transition-colors duration-200"
            aria-label="Toggle Theme"
            title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
        >
            {theme === 'light' ? (
                <Moon className="w-5 h-5 text-text-muted hover:text-primary" />
            ) : (
                <Sun className="w-5 h-5 text-text-muted hover:text-primary" />
            )}
        </button>
    );
};

export default ThemeToggle;
