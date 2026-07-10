import {
  BarChart as RechartsBar, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell,
} from "recharts";
import { useTheme } from "@/hooks/use-theme";
import { CHART_COLORS } from "@/lib/constants";

interface BarChartProps {
  data: Record<string, unknown>[];
  xKey: string;
  bars: { key: string; color?: string; name: string }[];
  height?: number;
  colors?: string[];
}

export function BarChart({ data, xKey, bars, height = 220, colors }: BarChartProps) {
  const { theme } = useTheme();
  const gridColor = theme === "dark" ? "hsl(0 0% 14%)" : "hsl(30 8% 88%)";
  const textColor = theme === "dark" ? "hsl(30 4% 52%)" : "hsl(20 5% 46%)";

  const defaultColors = [CHART_COLORS.primary, CHART_COLORS.secondary, CHART_COLORS.danger];

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsBar data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }} barSize={bars.length > 1 ? 12 : 20}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
        <XAxis
          dataKey={xKey}
          tick={{ fill: textColor, fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          interval={0}
          angle={data.length > 6 ? -30 : 0}
          textAnchor={data.length > 6 ? "end" : "middle"}
          height={data.length > 6 ? 50 : 30}
        />
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
        {bars.length > 1 && <Legend wrapperStyle={{ fontSize: "10px", paddingTop: "8px" }} />}
        {bars.map((b, bi) => (
          <Bar key={b.key} dataKey={b.key} name={b.name} fill={b.color || defaultColors[bi % defaultColors.length]} radius={[2, 2, 0, 0]}>
            {colors && data.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}
          </Bar>
        ))}
      </RechartsBar>
    </ResponsiveContainer>
  );
}
