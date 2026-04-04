import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useTheme } from '../context/ThemeContext';

const data = [
    { name: 'Jan', value: 400 },
    { name: 'Feb', value: 300 },
    { name: 'Mar', value: 600 },
    { name: 'Apr', value: 800 },
    { name: 'May', value: 500 },
    { name: 'Jun', value: 700 },
];

const ThemedChart = () => {
    const { theme } = useTheme();

    // Define colors based on the current theme
    // These should match or complement the CSS variables defined in index.css
    const axisColor = theme === 'dark' ? '#94a3b8' : '#64748b'; // text-muted
    const gridColor = theme === 'dark' ? '#334155' : '#e2e8f0'; // border
    const barColor = theme === 'dark' ? '#60a5fa' : '#3b82f6'; // primary
    const tooltipBg = theme === 'dark' ? '#1e293b' : '#ffffff'; // surface / bg
    const tooltipBorder = theme === 'dark' ? '#334155' : '#e2e8f0'; // border
    const tooltipText = theme === 'dark' ? '#f8fafc' : '#0f172a'; // text

    return (
        <div className="w-full h-[300px] p-4 bg-surface rounded-lg border border-border">
            <h3 className="text-lg font-semibold mb-4 text-text">Monthly Activity</h3>
            <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                    <XAxis dataKey="name" stroke={axisColor} />
                    <YAxis stroke={axisColor} />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: tooltipBg,
                            borderColor: tooltipBorder,
                            color: tooltipText,
                            borderRadius: '8px',
                        }}
                        itemStyle={{ color: tooltipText }}
                        cursor={{ fill: theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)' }}
                    />
                    <Bar dataKey="value" fill={barColor} radius={[4, 4, 0, 0]} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
};

export default ThemedChart;
