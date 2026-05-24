import { useEffect, useMemo, useState } from "react";
import { Brain, Play, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import { usePlatformStore } from "../store/usePlatformStore";
import { Button, Card, Input, Metric, Select } from "../components/ui";
import { EquityChart } from "../components/Charts";

type BacktestResult = {
  equity: number[];
  drawdown: number[];
  metrics: { return_pct: number; profit_usdt: number; max_drawdown_pct: number; sharpe: number; trades: number; win_rate: number };
  trades: Record<string, unknown>[];
  params?: Record<string, unknown>;
  effective_params?: Record<string, unknown>;
  preset_label?: string;
  preset_description?: string;
};

type IterationRow = {
  params: Record<string, unknown>;
  metrics: BacktestResult["metrics"];
  score: number;
  error?: string;
};

export default function Backtest() {
  const { strategies, refresh } = usePlatformStore();
  const [strategy, setStrategy] = useState("BB挤压突破.py");
  const [symbol, setSymbol] = useState("BTC/USDT:USDT");
  const [timeframe, setTimeframe] = useState("15m");
  const [initialCapital, setInitialCapital] = useState(10000);
  const [preset, setPreset] = useState("high_freq");
  const [startDate, setStartDate] = useState("2025-05-01");
  const [endDate, setEndDate] = useState("2026-05-14");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [iteration, setIteration] = useState<IterationRow[]>([]);

  useEffect(() => {
    refresh().catch(() => undefined);
  }, [refresh]);

  const selected = useMemo(() => strategies.find((item) => item.file === strategy), [strategies, strategy]);

  async function run() {
    setLoading(true);
    try {
      const data = await api<BacktestResult>("/api/backtest/run", {
        method: "POST",
        body: JSON.stringify({ strategy_file: strategy, symbol, timeframe, limit: 3000, initial_capital: initialCapital, preset, start_date: startDate, end_date: endDate, params: { symbol } })
      });
      setResult(data);
    } finally {
      setLoading(false);
    }
  }

  async function optimize() {
    setLoading(true);
    try {
      const data = await api<{ results: IterationRow[]; best: IterationRow }>("/api/backtest/iterate", {
        method: "POST",
        body: JSON.stringify({ strategy_file: strategy, symbol, timeframe, limit: 3000, initial_capital: initialCapital, start_date: startDate, end_date: endDate })
      });
      setIteration(data.results);
      if (data.best?.params) {
        const best = await api<BacktestResult>("/api/backtest/run", {
          method: "POST",
          body: JSON.stringify({ strategy_file: strategy, symbol, timeframe, limit: 3000, initial_capital: initialCapital, preset: "high_freq", start_date: startDate, end_date: endDate, params: data.best.params })
        });
        setResult(best);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
        <Card>
          <div className="mb-5">
            <h2 className="text-lg font-semibold">策略回测</h2>
            <p className="mt-1 text-sm text-app-muted">使用 D:\量化平台V2\data\smc_raw 的真实H1数据，可按日期切片。</p>
          </div>
          <div className="space-y-4">
            <label className="block text-sm text-app-muted">策略</label>
            <Select value={strategy} onChange={(event) => setStrategy(event.target.value)}>
              {strategies.map((item) => <option key={item.file}>{item.file}</option>)}
            </Select>
            <label className="block text-sm text-app-muted">标的</label>
            <Select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
              <option>BTC/USDT:USDT</option>
              <option>ETH/USDT:USDT</option>
              <option>SOL/USDT:USDT</option>
            </Select>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="mb-2 block text-sm text-app-muted">周期</label>
                <Select value={timeframe} onChange={(event) => setTimeframe(event.target.value)}>
                  <option value="15m">15m</option>
                  <option value="1h">1h</option>
                </Select>
              </div>
              <div>
                <label className="mb-2 block text-sm text-app-muted">本金</label>
                <Input type="number" value={initialCapital} onChange={(event) => setInitialCapital(Number(event.target.value))} />
              </div>
              <div>
                <label className="mb-2 block text-sm text-app-muted">参数包</label>
                <Select value={preset} onChange={(event) => setPreset(event.target.value)}>
                  <option value="high_freq">高频</option>
                  <option value="balanced">平衡</option>
                  <option value="stable">稳健</option>
                  <option value="conservative">保守</option>
                </Select>
              </div>
            </div>
            <div className="surface-soft rounded-xl p-3 text-xs text-app-muted">
              参数包不是新策略，而是同一策略的不同参数组合：高频提高交易次数，平衡折中，稳健更严格，保守更少交易。
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-2 block text-sm text-app-muted">开始日期</label>
                <Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
              </div>
              <div>
                <label className="mb-2 block text-sm text-app-muted">结束日期</label>
                <Input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
              </div>
            </div>
            <div className="surface-soft rounded-xl p-3 text-sm text-app-muted">
              <div className="text-[var(--app-text)]">{selected?.market_state || "HIGH_VOLATILITY"}</div>
              <div className="mt-1 line-clamp-4">{selected?.tags["核心逻辑"]}</div>
            </div>
            <Button onClick={run} disabled={loading} className="w-full"><Play size={16} />{loading ? "回测中" : "运行回测"}</Button>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="ghost" onClick={optimize} disabled={loading}><Sparkles size={16} />参数迭代</Button>
              <Button variant="ghost"><Brain size={16} />AI解读</Button>
            </div>
          </div>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold">权益曲线</h2>
          <p className="mb-4 text-sm text-app-muted">收益、回撤、交易明细同步生成。</p>
          {result ? <EquityChart equity={result.equity} drawdown={result.drawdown} /> : <div className="flex h-72 items-center justify-center rounded-xl border border-dashed border-[var(--app-line)] text-app-muted">点击运行回测生成曲线</div>}
        </Card>
      </div>
      <div className="grid gap-4 md:grid-cols-5">
        <Metric label="收益率" value={`${result?.metrics.return_pct ?? 0}%`} tone={(result?.metrics.return_pct ?? 0) >= 0 ? "up" : "down"} />
        <Metric label="盈利USDT" value={`${result?.metrics.profit_usdt ?? 0}`} tone={(result?.metrics.profit_usdt ?? 0) >= 0 ? "up" : "down"} />
        <Metric label="最大回撤" value={`${result?.metrics.max_drawdown_pct ?? 0}%`} tone="down" />
        <Metric label="夏普" value={`${result?.metrics.sharpe ?? 0}`} />
        <Metric label="交易数" value={`${result?.metrics.trades ?? 0}`} />
        <Metric label="胜率" value={`${result?.metrics.win_rate ?? 0}%`} tone="up" />
      </div>
      {iteration.length > 0 && (
        <Card>
          <h2 className="mb-4 text-lg font-semibold">参数迭代排行</h2>
          <div className="scrollbar max-h-72 overflow-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="text-app-muted"><tr><th className="py-2">评分</th><th>交易数</th><th>收益</th><th>胜率</th><th>回撤</th><th>参数</th></tr></thead>
              <tbody>
                {iteration.slice(0, 20).map((row, index) => (
                  <tr key={index} className="border-t border-[var(--app-line)]">
                    <td className="py-2">{row.score}</td>
                    <td>{row.metrics?.trades ?? "-"}</td>
                    <td>{row.metrics?.return_pct ?? "-"}%</td>
                    <td>{row.metrics?.win_rate ?? "-"}%</td>
                    <td>{row.metrics?.max_drawdown_pct ?? "-"}%</td>
                    <td className="max-w-md truncate text-app-muted">{JSON.stringify(row.params)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {result?.effective_params && (
        <Card>
          <h2 className="mb-2 text-lg font-semibold">最终使用参数</h2>
          <p className="mb-3 text-sm text-app-muted">{result.preset_label}：{result.preset_description}</p>
          <pre className="scrollbar max-h-72 overflow-auto whitespace-pre-wrap text-xs text-app-muted">{JSON.stringify(result.effective_params, null, 2)}</pre>
        </Card>
      )}
      <Card>
        <h2 className="mb-4 text-lg font-semibold">交易明细</h2>
        <div className="scrollbar max-h-72 overflow-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-app-muted"><tr><th className="py-2">序号</th><th>方向</th><th>入场</th><th>出场</th><th>盈亏</th><th>原始记录</th></tr></thead>
            <tbody>
              {(result?.trades || []).slice(-80).map((trade, index) => (
                <tr key={index} className="border-t border-[var(--app-line)]">
                  <td className="py-2">{index + 1}</td>
                  <td>{String(trade.side || trade.direction || trade.type || "-")}</td>
                  <td>{String(trade.entry_price || trade.entry || "-")}</td>
                  <td>{String(trade.exit_price || trade.exit || "-")}</td>
                  <td>{String(trade.pnl || trade.profit || "-")}</td>
                  <td className="max-w-md truncate text-app-muted">{JSON.stringify(trade)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
