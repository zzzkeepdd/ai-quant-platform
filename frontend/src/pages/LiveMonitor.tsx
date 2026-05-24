import { useEffect, useState } from "react";
import { AlertTriangle, Pause, Play, Square } from "lucide-react";
import { api } from "../lib/api";
import { usePlatformStore } from "../store/usePlatformStore";
import { Button, Card, Metric } from "../components/ui";

type AccountInfo = {
  equity: number;
  total: number;
  total_eq_usd?: number;
  source?: string;
  message?: string;
  error?: string;
  details?: AccountDetail[];
  funding_assets?: FundingAsset[];
};

type AccountDetail = {
  ccy?: string;
  eq?: string;
  cashBal?: string;
  availBal?: string;
  frozenBal?: string;
  upl?: string;
};

type FundingAsset = {
  ccy?: string;
  bal?: string;
  availBal?: string;
  frozenBal?: string;
};

type ActiveStrategy = {
  symbol?: string;
  market_state?: string;
  strategy?: string;
  parameter_version?: string;
  best_params?: Record<string, unknown>;
  score?: number;
  best_metrics?: Record<string, unknown>;
  risk_result?: string;
  applied_to_simulation?: boolean;
  updated_at?: string;
};

export default function LiveMonitor() {
  const { status, logs, pushLog, refresh, pageState, setPageState } = usePlatformStore();
  const cachedLive = (pageState.live as { account?: AccountInfo | null; positions?: unknown[]; orders?: unknown[] }) || {};
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [account, setAccount] = useState<AccountInfo | null>(cachedLive.account || null);
  const [positions, setPositions] = useState<unknown[]>(cachedLive.positions || []);
  const [orders, setOrders] = useState<unknown[]>(cachedLive.orders || []);

  async function loadExchangePanels() {
    const [accountData, positionsData, ordersData] = await Promise.all([
      api<AccountInfo>("/api/exchange/account"),
      api<unknown[]>("/api/exchange/positions"),
      api<unknown[]>("/api/exchange/orders")
    ]);
    setAccount(accountData);
    setPositions(positionsData);
    setOrders(ordersData);
    setPageState("live", { account: accountData, positions: positionsData, orders: ordersData });
  }

  useEffect(() => {
    loadExchangePanels().catch(() => undefined);
  }, []);

  async function start() {
    const result = await api<{ message: string }>("/api/trading/start", {
      method: "POST",
      body: JSON.stringify({ mode: "sandbox", position_mode: "固定", confirm: true })
    });
    pushLog(result.message);
    await refresh();
    await loadExchangePanels();
    setConfirmOpen(false);
  }

  async function control(path: string) {
    const result = await api<{ message: string }>(path, { method: "POST" });
    pushLog(result.message);
    await refresh();
  }

  const accountSourceLabel = account?.source === "okx_demo" ? "OKX 模拟盘 API" : account?.source === "okx_live" ? "OKX 实盘 API" : "未连接";
  const usdtDetail = account?.details?.find((item) => item.ccy === "USDT");
  const fundingAssets = (account?.funding_assets || []).filter((item) => Number(item.bal || item.availBal || 0) > 0);
  const activeStrategies = Object.values(status.trading?.active_strategies || {}) as ActiveStrategy[];

  return (
    <div className="space-y-5">
      {status.trading?.running && <Card className="border-yellow-500/25 bg-yellow-500/10 text-warning"><AlertTriangle className="mr-2 inline" size={18} />⚠️ 模拟盘自动交易运行中</Card>}
      <div className="grid gap-4 md:grid-cols-4">
        <Metric label="OKX 模拟盘交易账户权益" value={`${formatNumber(account?.equity)} USDT`} tone={account?.error ? "down" : "up"} />
        <Metric label="账户来源" value={accountSourceLabel} tone={account?.source?.startsWith("okx") ? "up" : "warn"} />
        <Metric label="美元总权益" value={`${formatNumber(account?.total_eq_usd ?? account?.total)} USD`} />
        <Metric label="USDT 可用余额" value={`${formatNumber(usdtDetail?.availBal ?? usdtDetail?.cashBal ?? account?.equity)} USDT`} />
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        <Metric label="市场状态" value={status.trading?.market_state || "RANGING"} />
        <Metric label="自动交易" value={status.trading?.running ? "运行中" : "已暂停"} tone={status.trading?.running ? "up" : "warn"} />
        <Metric label="连续失败" value={`${status.trading?.consecutive_failures ?? 0}`} tone={(status.trading?.consecutive_failures ?? 0) >= 3 ? "down" : "neutral"} />
      </div>
      {account?.message && <Card className="border-yellow-400/30 bg-yellow-400/10 text-sm text-yellow-200">{account.message}</Card>}
      {account?.error && <Card className="border-red-400/30 bg-red-400/10 text-sm text-red-200">{account.error}</Card>}
      <Card>
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">AI当前策略与参数</h2>
            <p className="text-sm text-app-muted">模拟盘自动采用；实盘只展示建议并等待人工确认。</p>
          </div>
          <span className="text-sm text-app-muted">{activeStrategies.length ? "已生成" : "等待自动优化"}</span>
        </div>
        {activeStrategies.length ? (
          <div className="overflow-auto">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="text-app-muted">
                <tr><th className="py-2">币种</th><th>状态</th><th>策略</th><th>评分</th><th>交易/胜率</th><th>风控</th><th>参数版本</th><th>更新时间</th></tr>
              </thead>
              <tbody>
                {activeStrategies.map((row) => (
                  <tr key={row.symbol} className="border-t border-[var(--app-line)]">
                    <td className="py-2 font-medium">{row.symbol || "-"}</td>
                    <td>{row.market_state || "-"}</td>
                    <td>{row.strategy || "-"}</td>
                    <td>{formatNumber(row.score)}</td>
                    <td>{String(row.best_metrics?.trades ?? 0)} / {String(row.best_metrics?.win_rate ?? 0)}%</td>
                    <td>{row.risk_result || "-"}</td>
                    <td className="max-w-sm truncate text-app-muted">{row.parameter_version || "-"}</td>
                    <td className="text-app-muted">{row.updated_at || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-[var(--app-line)] p-4 text-sm text-app-muted">启动模拟盘自动交易后，系统会按OKX行情自动选择策略并迭代参数。</div>
        )}
      </Card>
      <Card>
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">OKX 账户资金</h2>
          <span className="text-sm text-app-muted">{accountSourceLabel}</span>
        </div>
        <div className="surface-soft mb-4 rounded-xl p-3 text-sm text-app-muted">交易账户和资金账户是OKX两个口径；下方资金账户资产对应你截图里的小额USDT/SOL，交易账户权益来自OKX模拟盘合约账户。</div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="交易账户明细">
            {account?.details?.length ? <AssetTable rows={account.details.map((item) => ({
              ccy: item.ccy,
              equity: item.eq,
              available: item.availBal ?? item.cashBal,
              frozen: item.frozenBal,
              pnl: item.upl
            }))} /> : "未读取到 OKX 交易账户明细。"}
          </Panel>
          <Panel title="资金账户资产">
            {fundingAssets.length ? <AssetTable rows={fundingAssets.map((item) => ({
              ccy: item.ccy,
              equity: item.bal,
              available: item.availBal,
              frozen: item.frozenBal
            }))} /> : "OKX 资金账户暂无可显示资产。"}
          </Panel>
        </div>
      </Card>
      <Card>
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">自动交易控制</h2>
            <p className="text-sm text-app-muted">不逐单确认，但每次启动必须确认，连续3次失败自动暂停。</p>
          </div>
          <div className="flex gap-2">
            <Button onClick={() => setConfirmOpen(true)}><Play size={16} />启动</Button>
            <Button variant="ghost" onClick={() => control("/api/trading/pause")}><Pause size={16} />暂停</Button>
            <Button variant="danger" onClick={() => control("/api/trading/stop")}><Square size={16} />停止</Button>
          </div>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <Panel title="持仓">{positions.length ? <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(positions.slice(0, 4), null, 2)}</pre> : "当前 OKX 模拟盘无持仓。"}</Panel>
          <Panel title="挂单">{orders.length ? <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(orders.slice(0, 4), null, 2)}</pre> : "当前 OKX 模拟盘无挂单。"}</Panel>
          <Panel title="交易日志">{logs.length ? logs.map((line) => <div key={line}>{line}</div>) : "暂无日志。"}</Panel>
        </div>
      </Card>
      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-5">
          <Card className="max-w-lg">
            <h3 className="text-xl font-semibold text-warning">确认启动模拟盘自动交易</h3>
            <p className="mt-3 text-sm leading-6 text-app-muted">系统将由DeepSeek判断行情，由策略生成信号，并由风控守卫自动审核。模拟盘不会使用真实资金，但仍会调用OKX模拟交易API。</p>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setConfirmOpen(false)}>取消</Button>
              <Button variant="warn" onClick={start}>确认启动</Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

function Panel({ title, children }: React.PropsWithChildren<{ title: string }>) {
  return <div className="surface-soft scrollbar min-h-44 overflow-auto rounded-xl p-4 text-sm text-app-muted"><div className="mb-3 font-medium text-[var(--app-text)]">{title}</div>{children}</div>;
}

function AssetTable({ rows }: { rows: { ccy?: string; equity?: string; available?: string; frozen?: string; pnl?: string }[] }) {
  return (
    <div className="overflow-auto">
      <table className="w-full min-w-[520px] text-left text-xs">
        <thead className="text-app-muted">
          <tr>
            <th className="py-2 pr-3 font-medium">币种</th>
            <th className="py-2 pr-3 font-medium">权益/余额</th>
            <th className="py-2 pr-3 font-medium">可用</th>
            <th className="py-2 pr-3 font-medium">冻结</th>
            <th className="py-2 pr-3 font-medium">未实现盈亏</th>
          </tr>
        </thead>
        <tbody className="text-[var(--app-text)]">
          {rows.map((row) => (
            <tr key={row.ccy} className="border-t border-[var(--app-line)]">
              <td className="py-2 pr-3 font-medium">{row.ccy || "-"}</td>
              <td className="py-2 pr-3">{formatNumber(row.equity)}</td>
              <td className="py-2 pr-3">{formatNumber(row.available)}</td>
              <td className="py-2 pr-3">{formatNumber(row.frozen)}</td>
              <td className="py-2 pr-3">{formatNumber(row.pnl)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatNumber(value?: number | string) {
  const numberValue = Number(value ?? 0);
  if (!Number.isFinite(numberValue)) return "0.00";
  return numberValue.toLocaleString("en-US", { maximumFractionDigits: 6 });
}
