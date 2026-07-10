import {
  AreaChart as RechartsArea, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { useTheme } from "@/hooks/use-theme";
import { CHART_COLORS } from "@/lib/constants";

interface AreaChartProps {
  data: Record<string, unknown>[];
  xKey: string;
  areas: { key: string; color?: string; name: string }[];
  height?: number;
}

export function AreaChart({ data, xKey, areas, height = 220 }: AreaChartProps) {
  const { theme } = useTheme();
  const gridColor = theme === "dark" ? "hsl(0 0% 14%)" : "hsl(30 8% 88%)";
  const textColor = theme === "dark" ? "hsl(30 4% 52%)" : "hsl(20 5% 46%)";

  const defaultColors = [CHART_COLORS.primary, CHART_COLORS.success, CHART_COLORS.secondary];

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsArea data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
        <defs>
          {areas.map((a, i) => {
            const color = a.color || defaultColors[i % defaultColors.length];
            return (
              <linearGradient key={a.key} id={`gradient-${a.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.2} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            );
          })}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
        <XAxis dataKey={xKey} tick={{ fill: textColor, fontSize: 10 }} tickLine={false} axisLine={false} />
        <YAxis tick={{ fill: textColor, fontSize: 10 }} tickLine={false} axisLine={false} width={32} />
        <Tooltip
          contentStyle={{
            backgroundColor: theme === "dark" ? "hsl(0 0% 8%)" : "hsl(30 10% 99%)",
            border: `1px solid ${gridColor}`,
            borderRadius: "6px",
            fontSize: "11px",
            padding: "6px 10px",
          }}
        />
        <Legend wrapperStyle={{ fontSize: "10px", paddingTop: "8px" }} />
        {areas.map((a, i) => {
          const color = a.color || defaultColors[i % defaultColors.length];
          return (
            <Area
              key={a.key}
              type="monotone"
              dataKey={a.key}
              name={a.name}
              stroke={color}
              fill={`url(#gradient-${a.key})`}
              strokeWidth={1.5}
            />
          );
        })}
      </RechartsArea>
    </ResponsiveContainer>
  );
}
