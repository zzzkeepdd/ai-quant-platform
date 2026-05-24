import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const tooltipStyle = { background: "#18181b", border: "1px solid rgba(255,255,255,.12)", borderRadius: 12, color: "#fff" };

export function EquityChart({ equity, drawdown }: { equity: number[]; drawdown?: number[] }) {
  const data = equity.map((value, index) => ({ index, equity: value, drawdown: drawdown?.[index] ?? 0 }));
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="equity" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22c55e" stopOpacity={0.42} />
              <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(255,255,255,.06)" />
          <XAxis dataKey="index" stroke="#71717a" tick={{ fontSize: 12 }} />
          <YAxis stroke="#71717a" tick={{ fontSize: 12 }} />
          <Tooltip contentStyle={tooltipStyle} />
          <Area type="monotone" dataKey="equity" stroke="#22c55e" fill="url(#equity)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CompareChart({ series }: { series: number[] }) {
  const data = series.map((value, index) => ({ index, value }));
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid stroke="rgba(255,255,255,.06)" />
          <XAxis dataKey="index" stroke="#71717a" tick={{ fontSize: 12 }} />
          <YAxis stroke="#71717a" tick={{ fontSize: 12 }} />
          <Tooltip contentStyle={tooltipStyle} />
          <Line type="monotone" dataKey="value" stroke="#60a5fa" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
