import { useState } from "react";
import { Play } from "lucide-react";
import { api } from "../lib/api";
import { usePlatformStore } from "../store/usePlatformStore";
import { Button, Card, Input, Metric, Select } from "../components/ui";
import { CompareChart } from "../components/Charts";

type ReplayResult = {
  equity: number[];
  decisions: { bar: number; price: number; market_state: string; strategy: string; parameter_version?: string; reason: string }[];
  trades: Record<string, unknown>[];
  strategy_stats: Record<string, { trades: number; win_rate: number; profit_usdt: number; max_drawdown_pct: number }>;
  strategy_switches: { bar: number; time: string; market_state: string; strategy: string; reason: string }[];
  active_strategy_stats: Record<string, { trades: number; win_rate: number; profit_usdt: number; max_drawdown_pct: number; return_pct?: number }>;
  candidate_metrics: Record<string, unknown>;
  metrics: { return_pct: number; profit_usdt: number; max_drawdown_pct: number; sharpe: number; trades: number; win_rate: number };
};

export default function Replay() {
  const { pageState, setPageState } = usePlatformStore();
  const cached = (pageState.replay as {
    symbol?: string;
    timeframe?: string;
    initialCapital?: number;
    startDate?: string;
    endDate?: string;
    result?: ReplayResult | null;
  }) || {};
  const [symbol, setSymbolValue] = useState(cached.symbol || "BTC/USDT:USDT");
  const [timeframe, setTimeframeValue] = useState(cached.timeframe || "15m");
  const [initialCapital, setInitialCapitalValue] = useState(cached.initialCapital || 10000);
  const [startDate, setStartDateValue] = useState(cached.startDate || "2025-05-01");
  const [endDate, setEndDateValue] = useState(cached.endDate || "2026-05-14");
  const [result, setResultValue] = useState<ReplayResult | null>(cached.result || null);

  function cache(next: Record<string, unknown>) {
    setPageState("replay", { symbol, timeframe, initialCapital, startDate, endDate, result, ...next });
  }

  function setSymbol(next: string) {
    setSymbolValue(next);
    cache({ symbol: next });
  }

  function setTimeframe(next: string) {
    setTimeframeValue(next);
    cache({ timeframe: next });
  }

  function setInitialCapital(next: number) {
    setInitialCapitalValue(next);
    cache({ initialCapital: next });
  }

  function setStartDate(next: string) {
    setStartDateValue(next);
    cache({ startDate: next });
  }

  function setEndDate(next: string) {
    setEndDateValue(next);
    cache({ endDate: next });
  }

  async function run() {
    const data = await api<ReplayResult>("/api/replay/run", {
      method: "POST",
      body: JSON.stringify({ symbol, strategy_file: "BOS移动止损增强版.py", timeframe, initial_capital: initialCapital, candles: 1000, start_date: startDate, end_date: endDate })
    });
    setResultValue(data);
    cache({ result: data });
  }

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">历史重放</h2>
            <p className="text-sm text-app-muted">按日期范围逐根K线回放AI状态判断、策略切换和权益变化。</p>
          </div>
          <div className="grid gap-2 md:grid-cols-[150px_110px_130px_150px_150px_auto]">
            <Select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
              <option>BTC/USDT:USDT</option>
              <option>ETH/USDT:USDT</option>
              <option>SOL/USDT:USDT</option>
            </Select>
            <Select value={timeframe} onChange={(event) => setTimeframe(event.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
            </Select>
            <Input type="number" value={initialCapital} onChange={(event) => setInitialCapital(Number(event.target.value))} />
            <Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            <Input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
            <Button onClick={run}><Play size={16} />开始重放</Button>
          </div>
        </div>
      </Card>
      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="重放收益" value={`${result?.metrics.return_pct ?? 0}%`} tone="up" />
        <Metric label="盈利USDT" value={`${result?.metrics.profit_usdt ?? 0}`} tone={(result?.metrics.profit_usdt ?? 0) >= 0 ? "up" : "down"} />
        <Metric label="最大回撤" value={`${result?.metrics.max_drawdown_pct ?? 0}%`} tone="down" />
        <Metric label="交易数/胜率" value={`${result?.metrics.trades ?? 0} / ${result?.metrics.win_rate ?? 0}%`} />
        <Metric label="决策次数" value={`${result?.decisions.length ?? 0}`} />
      </div>
      <Card>
        <h2 className="mb-4 text-lg font-semibold">策略切换记录</h2>
        <div className="scrollbar max-h-72 overflow-auto">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="text-app-muted"><tr><th className="py-2">K线</th><th>时间</th><th>状态</th><th>执行策略</th><th>原因</th></tr></thead>
            <tbody>
              {(result?.strategy_switches || []).map((row, index) => (
                <tr key={index} className="border-t border-[var(--app-line)]">
                  <td className="py-2">{row.bar}</td><td>{row.time}</td><td>{row.market_state}</td><td>{row.strategy}</td><td>{row.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card>
        <h2 className="mb-4 text-lg font-semibold">AI决策对比曲线</h2>
        {result ? <CompareChart series={result.equity} /> : <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-[var(--app-line)] text-app-muted">等待重放结果</div>}
      </Card>
      <Card>
        <h2 className="mb-4 text-lg font-semibold">决策日志</h2>
        <div className="scrollbar max-h-80 overflow-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-app-muted"><tr><th className="py-2">K线</th><th>价格</th><th>状态</th><th>策略</th><th>参数</th><th>原因</th></tr></thead>
            <tbody>
              {(result?.decisions || []).map((row) => (
                <tr key={row.bar} className="border-t border-[var(--app-line)]"><td className="py-2">{row.bar}</td><td>{row.price}</td><td>{row.market_state}</td><td>{row.strategy}</td><td>{row.parameter_version || "-"}</td><td>{row.reason}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card>
        <h2 className="mb-4 text-lg font-semibold">交易统计与明细</h2>
        <pre className="mb-4 whitespace-pre-wrap text-xs text-app-muted">{JSON.stringify(result?.active_strategy_stats || {}, null, 2)}</pre>
        <div className="scrollbar max-h-72 overflow-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-app-muted"><tr><th className="py-2">方向</th><th>入场</th><th>出场</th><th>盈亏%</th><th>结果</th></tr></thead>
            <tbody>
              {(result?.trades || []).slice(-80).map((trade, index) => (
                <tr key={index} className="border-t border-[var(--app-line)]">
                  <td className="py-2">{String(trade.type || trade.side || "-")}</td>
                  <td>{String(trade.entry_price || trade.entry || "-")}</td>
                  <td>{String(trade.exit_price || trade.exit || trade.tp || "-")}</td>
                  <td>{String(trade.pnl_pct || trade.pnl || "-")}</td>
                  <td>{String(trade.result || trade.res || "-")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
