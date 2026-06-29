import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ResumoAno } from "../types";

export function ChartAnos({ data }: { data: ResumoAno[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e7e0d4" />
        <XAxis dataKey="ano" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
        <Tooltip
          formatter={(v: number) => [v.toLocaleString("pt-BR"), "Notificações"]}
          labelFormatter={(l) => `Ano ${l}`}
        />
        <Bar dataKey="registros" fill="#9f1239" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ChartSemanas({
  data,
  seriesLabel = "Casos",
  activeSemana,
  onSemanaSelect,
}: {
  data: { semana: number; casos: number }[];
  seriesLabel?: string;
  activeSemana?: number;
  onSemanaSelect?: (index: number) => void;
}) {
  const activeIndex = data.findIndex((d) => d.semana === activeSemana);

  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart
        data={data}
        margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
        onClick={(state) => {
          const idx = state?.activeTooltipIndex;
          if (typeof idx === "number" && onSemanaSelect) onSemanaSelect(idx);
        }}
        style={{ cursor: onSemanaSelect ? "pointer" : undefined }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e7e0d4" />
        <XAxis
          dataKey="semana"
          tick={{ fontSize: 11 }}
          label={{ value: "Semana", position: "insideBottom", offset: -2 }}
        />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v: number) => [v.toLocaleString("pt-BR"), seriesLabel]} />
        {activeSemana != null && (
          <ReferenceLine x={activeSemana} stroke="#9f1239" strokeWidth={2} strokeDasharray="4 3" />
        )}
        <Line
          type="monotone"
          dataKey="casos"
          stroke="#2166ac"
          strokeWidth={2}
          dot={({ cx, cy, index }) => {
            if (cx == null || cy == null) return <g />;
            const active = index === activeIndex;
            return (
              <circle
                key={`dot-${index}`}
                cx={cx}
                cy={cy}
                r={active ? 6 : 2.5}
                fill={active ? "#9f1239" : "#2166ac"}
                stroke={active ? "#fff" : "none"}
                strokeWidth={2}
                style={{ cursor: onSemanaSelect ? "pointer" : undefined }}
                onClick={(e) => {
                  e.stopPropagation();
                  onSemanaSelect?.(index);
                }}
              />
            );
          }}
          activeDot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
