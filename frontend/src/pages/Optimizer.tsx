import { useState } from "react";
import { Sparkles } from "lucide-react";
import { api } from "../lib/api";
import { usePlatformStore } from "../store/usePlatformStore";
import { Button, Card, Input, Select } from "../components/ui";

type IterationRow = {
  params: Record<string, unknown>;
  metrics: { return_pct?: number; profit_usdt?: number; max_drawdown_pct?: number; trades?: number; win_rate?: number };
  score: number;
};

type AutoOptimizationRow = {
  symbol: string;
  timeframe: string;
  market_state: string;
  state_reason: string;
  strategy: string;
  best_params: Record<string, unknown>;
  best_metrics: { return_pct?: number; profit_usdt?: number; max_drawdown_pct?: number; trades?: number; win_rate?: number };
  score: number;
  parameter_version: string;
  data_source?: string;
  recommended_action: string;
  applied_to_simulation: boolean;
  updated_at: string;
  iteration: { results: IterationRow[]; trade_count_quality?: string; overfit_warning?: string; selected_reason?: string };
};

type AutoOptimizationResult = {
  results: AutoOptimizationRow[];
  updated_at: string;
};

type OptimizerState = {
  symbol: string;
  timeframe: string;
  initialCapital: number;
  result: AutoOptimizationResult | null;
};

const defaults: OptimizerState = {
  symbol: "ALL",
  timeframe: "15m",
  initialCapital: 10000,
  result: null
};

export default function Optimizer() {
  const { pageState, setPageState } = usePlatformStore();
  const cached = { ...defaults, ...((pageState.optimizer as Partial<OptimizerState>) || {}) };
  const [symbol, setSymbolValue] = useState(cached.symbol);
  const [timeframe, setTimeframeValue] = useState(cached.timeframe);
  const [initialCapital, setInitialCapitalValue] = useState(cached.initialCapital);
  const [result, setResultValue] = useState<AutoOptimizationResult | null>(cached.result || null);
  const [loading, setLoading] = useState(false);

  function cache(next: Partial<OptimizerState>) {
    setPageState("optimizer", { symbol, timeframe, initialCapital, result, ...next });
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

  async function runOptimization() {
    setLoading(true);
    try {
      const data = await api<AutoOptimizationResult>("/api/ai/auto-optimize", {
        method: "POST",
        body: JSON.stringify({ symbol, timeframe, initial_capital: initialCapital })
      });
      setResultValue(data);
      cache({ result: data });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold"><Sparkles size={20} />AI参数迭代</h2>
            <p className="mt-1 text-sm text-app-muted">从OKX最新K线判断行情状态，自动选择候选策略，再单独跑参数网格和综合评分。</p>
          </div>
          <div className="grid w-full gap-2 md:w-auto md:grid-cols-[180px_110px_130px_auto]">
            <Select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
              <option value="ALL">BTC + ETH + SOL</option>
              <option>BTC/USDT:USDT</option>
              <option>ETH/USDT:USDT</option>
              <option>SOL/USDT:USDT</option>
            </Select>
            <Select value={timeframe} onChange={(event) => setTimeframe(event.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
            </Select>
            <Input type="number" value={initialCapital} onChange={(event) => setInitialCapital(Number(event.target.value))} />
            <Button onClick={runOptimization} disabled={loading}><Sparkles size={16} />{loading ? "迭代中" : "开始迭代"}</Button>
          </div>
        </div>
      </Card>

      {result ? <OptimizationView data={result} /> : (
        <Card>
          <div className="rounded-xl border border-dashed border-[var(--app-line)] p-6 text-center text-sm text-app-muted">等待参数迭代结果。这里不会混入行情分析长文本，只展示策略选择、参数排行和评分证据。</div>
        </Card>
      )}
    </div>
  );
}

function OptimizationView({ data }: { data: AutoOptimizationResult }) {
  return (
    <div className="space-y-4">
      {data.results.map((row) => (
        <Card key={row.symbol}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-lg font-semibold">{row.symbol}</div>
              <div className="mt-1 text-sm text-app-muted">{row.market_state} · {row.strategy}</div>
            </div>
            <div className="text-right text-sm">
              <div className="text-success">评分 {formatNumber(row.score)}</div>
              <div className="text-app-muted">{row.data_source}</div>
            </div>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-4">
            <SmallMetric label="收益" value={`${row.best_metrics.return_pct ?? 0}%`} />
            <SmallMetric label="回撤" value={`${row.best_metrics.max_drawdown_pct ?? 0}%`} />
            <SmallMetric label="交易数" value={`${row.best_metrics.trades ?? 0}`} />
            <SmallMetric label="胜率" value={`${row.best_metrics.win_rate ?? 0}%`} />
          </div>
          <div className="surface-soft mt-3 rounded-lg p-3 text-xs text-app-muted">
            <div className="mb-2 text-[var(--app-text)]">最优参数</div>
            <pre className="scrollbar max-h-28 overflow-auto whitespace-pre-wrap">{JSON.stringify(row.best_params, null, 2)}</pre>
          </div>
          <div className="mt-3 text-sm text-app-muted">{row.state_reason}</div>
          <div className="mt-1 text-sm text-app-muted">{row.iteration.selected_reason}</div>
          <div className="mt-1 text-sm text-warning">{row.iteration.overfit_warning}</div>
          <div className="mt-3 overflow-auto">
            <table className="w-full min-w-[620px] text-left text-xs">
              <thead className="text-app-muted"><tr><th className="py-2">评分</th><th>交易</th><th>收益</th><th>胜率</th><th>回撤</th><th>参数</th></tr></thead>
              <tbody>
                {(row.iteration.results || []).slice(0, 10).map((item, index) => (
                  <tr key={index} className="border-t border-[var(--app-line)]">
                    <td className="py-2">{formatNumber(item.score)}</td>
                    <td>{item.metrics?.trades ?? 0}</td>
                    <td>{item.metrics?.return_pct ?? 0}%</td>
                    <td>{item.metrics?.win_rate ?? 0}%</td>
                    <td>{item.metrics?.max_drawdown_pct ?? 0}%</td>
                    <td className="max-w-sm truncate text-app-muted">{JSON.stringify(item.params)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
    </div>
  );
}

function SmallMetric({ label, value }: { label: string; value: string }) {
  return <div className="surface-soft rounded-lg p-3"><div className="text-xs text-app-muted">{label}</div><div className="mt-1 text-xl font-semibold">{value}</div></div>;
}

function formatNumber(value: number) {
  return Number(value || 0).toLocaleString("en-US", { maximumFractionDigits: 4 });
}
