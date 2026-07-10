import { PieChart as RechartsPie, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { useTheme } from "@/hooks/use-theme";
import { CATEGORY_COLORS, CHART_PALETTE } from "@/lib/constants";
import { categoryLabel } from "@/lib/utils";

interface PieChartProps {
  data: { name: string; value: number }[];
  height?: number;
  useCategoryColors?: boolean;
}

export function PieChart({ data, height = 200, useCategoryColors = false }: PieChartProps) {
  const { theme } = useTheme();

  const colored = data.map((d, i) => ({
    ...d,
    label: categoryLabel(d.name),
    fill: useCategoryColors ? (CATEGORY_COLORS[d.name] || CHART_PALETTE[i % CHART_PALETTE.length]) : CHART_PALETTE[i % CHART_PALETTE.length],
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsPie>
        <Pie
          data={colored}
          cx="50%"
          cy="50%"
          innerRadius={48}
          outerRadius={72}
          paddingAngle={2}
          dataKey="value"
          nameKey="label"
          strokeWidth={0}
        >
          {colored.map((entry, i) => (
            <Cell key={i} fill={entry.fill} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: theme === "dark" ? "hsl(0 0% 8%)" : "hsl(30 10% 99%)",
            border: `1px solid ${theme === "dark" ? "hsl(0 0% 14%)" : "hsl(30 8% 88%)"}`,
            borderRadius: "6px",
            fontSize: "11px",
            padding: "6px 10px",
          }}
        />
        <Legend wrapperStyle={{ fontSize: "10px" }} />
      </RechartsPie>
    </ResponsiveContainer>
  );
}
