import { useEffect, useState, type PropsWithChildren } from "react";
import { AlertTriangle, Pause, Play, RefreshCw, Square } from "lucide-react";
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

type AccountDetail = { ccy?: string; eq?: string; cashBal?: string; availBal?: string; frozenBal?: string; upl?: string };
type FundingAsset = { ccy?: string; bal?: string; availBal?: string; frozenBal?: string };
type ActiveStrategy = { symbol?: string; market_state?: string; strategy?: string; parameter_version?: string; score?: number; best_metrics?: Record<string, unknown>; risk_result?: string; updated_at?: string };
type MarketRow = { symbol: string; inst_id: string; last?: number | null; change_24h_pct?: number | null; volume_24h?: number | null; bid?: number | null; ask?: number | null; source: string; updated_at: string };
type OnchainRow = { asset: string; chain: string; raw_chain?: string; tvl?: number | null; change_1d_pct?: number | null; change_7d_pct?: number | null; protocols?: number; source: string; updated_at: string };
type DataResponse<T> = { ok: boolean; source: string; data: T[]; errors?: string[]; updated_at: string; stale?: boolean };
type TestOrderResponse = { ok: boolean; message: string; order?: Record<string, unknown>; response?: { data?: { ordId?: string; sMsg?: string; sCode?: string }[] } };
type LivePageCache = { account?: AccountInfo | null; positions?: unknown[]; orders?: unknown[]; market?: DataResponse<MarketRow> | null; onchain?: DataResponse<OnchainRow> | null };

export default function LiveMonitor() {
  const { status, logs, pushLog, refresh, pageState, setPageState } = usePlatformStore();
  const cachedLive = (pageState.live as LivePageCache) || {};
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [testOrderOpen, setTestOrderOpen] = useState(false);
  const [testOrderBusy, setTestOrderBusy] = useState(false);
  const [testOrderResult, setTestOrderResult] = useState<TestOrderResponse | null>(null);
  const [account, setAccount] = useState<AccountInfo | null>(cachedLive.account || null);
  const [positions, setPositions] = useState<unknown[]>(cachedLive.positions || []);
  const [orders, setOrders] = useState<unknown[]>(cachedLive.orders || []);
  const [market, setMarket] = useState<DataResponse<MarketRow> | null>(cachedLive.market || null);
  const [onchain, setOnchain] = useState<DataResponse<OnchainRow> | null>(cachedLive.onchain || null);
  const [loadingData, setLoadingData] = useState(false);

  async function loadLivePanels() {
    setLoadingData(true);
    try {
      const [accountData, positionsData, ordersData, marketData, onchainData] = await Promise.all([
        api<AccountInfo>("/api/exchange/account"),
        api<unknown[]>("/api/exchange/positions"),
        api<unknown[]>("/api/exchange/orders"),
        api<DataResponse<MarketRow>>("/api/market/live"),
        api<DataResponse<OnchainRow>>("/api/onchain/summary")
      ]);
      setAccount(accountData);
      setPositions(positionsData);
      setOrders(ordersData);
      setMarket(marketData);
      setOnchain(onchainData);
      setPageState("live", { account: accountData, positions: positionsData, orders: ordersData, market: marketData, onchain: onchainData });
    } finally {
      setLoadingData(false);
    }
  }

  useEffect(() => {
    loadLivePanels().catch((error) => pushLog(`实时数据刷新失败：${String(error).slice(0, 120)}`));
  }, []);

  async function start() {
    const result = await api<{ message: string }>("/api/trading/start", {
      method: "POST",
      body: JSON.stringify({ mode: "sandbox", position_mode: "固定", confirm: true })
    });
    pushLog(result.message);
    await refresh();
    await loadLivePanels();
    setConfirmOpen(false);
  }

  async function control(path: string) {
    const result = await api<{ message: string }>(path, { method: "POST" });
    pushLog(result.message);
    await refresh();
  }

  async function placeTestOrder() {
    setTestOrderBusy(true);
    setTestOrderResult(null);
    try {
      const result = await api<TestOrderResponse>("/api/trading/test-order", {
        method: "POST",
        body: JSON.stringify({ inst_id: "SOL-USDT-SWAP", side: "buy", size: "1", td_mode: "cross", confirm: true })
      });
      setTestOrderResult(result);
      pushLog(result.message);
      await refresh();
      await loadLivePanels();
    } catch (error) {
      const message = `OKX模拟盘测试下单失败：${String(error).slice(0, 180)}`;
      setTestOrderResult({ ok: false, message });
      pushLog(message);
    } finally {
      setTestOrderBusy(false);
    }
  }

  const accountSourceLabel = account?.source === "okx_demo" ? "OKX 模拟盘 API" : account?.source === "okx_live" ? "OKX 实盘 API" : "未连接";
  const fundingAssets = (account?.funding_assets || []).filter((item) => Number(item.bal || item.availBal || 0) > 0);
  const activeStrategies = Object.values(status.trading?.active_strategies || {}) as ActiveStrategy[];
  const firstMarket = market?.data?.[0];
  const firstOnchain = onchain?.data?.[0];

  return (
    <div className="space-y-5">
      {status.trading?.running && <Card className="border-yellow-500/25 bg-yellow-500/10 text-warning"><AlertTriangle className="mr-2 inline" size={18} />模拟盘自动交易运行中</Card>}

      <div className="grid gap-4 md:grid-cols-4">
        <Metric label="OKX 账户权益" value={`${formatNumber(account?.equity)} USDT`} tone={account?.error ? "down" : "up"} />
        <Metric label="账户来源" value={accountSourceLabel} tone={account?.source?.startsWith("okx") ? "up" : "warn"} />
        <Metric label="BTC 最新价" value={firstMarket ? `$${formatNumber(firstMarket.last)}` : "--"} />
        <Metric label="链上 TVL 样本" value={firstOnchain ? `$${compactNumber(firstOnchain.tvl)}` : "--"} />
      </div>

      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">真实行情与链上数据</h2>
            <p className="text-sm text-app-muted">AI 分析会同时读取 OKX K线、OKX 实时 ticker、DefiLlama 链上 TVL 摘要。</p>
          </div>
          <Button variant="ghost" onClick={() => loadLivePanels().catch((error) => pushLog(`实时数据刷新失败：${String(error).slice(0, 120)}`))} disabled={loadingData}>
            <RefreshCw size={16} />刷新
          </Button>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          <Panel title={`OKX 实时行情${market?.stale ? "（缓存）" : ""}`}>
            <StatusLine source={market?.source} updatedAt={market?.updated_at} errors={market?.errors} />
            <MarketTable rows={market?.data || []} />
          </Panel>
          <Panel title={`链上数据${onchain?.stale ? "（缓存）" : ""}`}>
            <StatusLine source={onchain?.source} updatedAt={onchain?.updated_at} errors={onchain?.errors} />
            <OnchainTable rows={onchain?.data || []} />
          </Panel>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="市场状态" value={status.trading?.market_state || "RANGING"} />
        <Metric label="自动交易" value={status.trading?.running ? "运行中" : "已暂停"} tone={status.trading?.running ? "up" : "warn"} />
        <Metric label="连续失败" value={`${status.trading?.consecutive_failures ?? 0}`} tone={(status.trading?.consecutive_failures ?? 0) >= 3 ? "down" : "neutral"} />
      </div>

      {account?.message && <Card className="border-yellow-400/30 bg-yellow-400/10 text-sm text-yellow-200">{account.message}</Card>}
      {account?.error && <Card className="border-red-400/30 bg-red-400/10 text-sm text-red-200">{account.error}</Card>}

      <Card>
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">AI 当前策略与参数</h2>
            <p className="text-sm text-app-muted">模拟盘可自动采用建议；实盘仍需要人工确认。</p>
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
                    <td className="text-app-muted">{formatDate(row.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-[var(--app-line)] p-4 text-sm text-app-muted">启动模拟盘自动交易后，系统会按 OKX 行情自动选择策略并迭代参数。</div>
        )}
      </Card>

      <Card>
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">OKX 账户资金</h2>
          <span className="text-sm text-app-muted">{accountSourceLabel}</span>
        </div>
        <div className="surface-soft mb-4 rounded-xl p-3 text-sm text-app-muted">交易账户和资金账户是 OKX 两个口径；下方资金账户资产来自 OKX 私有读取接口。</div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="交易账户明细">
            {account?.details?.length ? <AssetTable rows={account.details.map((item) => ({ ccy: item.ccy, equity: item.eq, available: item.availBal ?? item.cashBal, frozen: item.frozenBal, pnl: item.upl }))} /> : "未读取到 OKX 交易账户明细。"}
          </Panel>
          <Panel title="资金账户资产">
            {fundingAssets.length ? <AssetTable rows={fundingAssets.map((item) => ({ ccy: item.ccy, equity: item.bal, available: item.availBal, frozen: item.frozenBal }))} /> : "OKX 资金账户暂无可显示资产。"}
          </Panel>
        </div>
      </Card>

      <Card>
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">自动交易控制</h2>
            <p className="text-sm text-app-muted">“测试下单”会真实调用 OKX 模拟盘 REST，你可以在交易所模拟盘看到订单/持仓变化。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setConfirmOpen(true)}><Play size={16} />启动</Button>
            <Button variant="warn" onClick={() => setTestOrderOpen(true)}><Play size={16} />测试下单</Button>
            <Button variant="ghost" onClick={() => control("/api/trading/pause")}><Pause size={16} />暂停</Button>
            <Button variant="danger" onClick={() => control("/api/trading/stop")}><Square size={16} />停止</Button>
          </div>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <Panel title="持仓">{positions.length ? <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(positions.slice(0, 4), null, 2)}</pre> : "当前 OKX 无持仓或未读取到持仓。"}</Panel>
          <Panel title="挂单">{orders.length ? <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(orders.slice(0, 4), null, 2)}</pre> : "当前 OKX 无挂单或未读取到挂单。"}</Panel>
          <Panel title="交易日志">{logs.length ? logs.map((line) => <div key={line}>{line}</div>) : "暂无日志。"}</Panel>
        </div>
      </Card>

      {testOrderOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-5">
          <Card className="max-w-lg">
            <h3 className="text-xl font-semibold text-warning">确认 OKX 模拟盘测试下单</h3>
            <p className="mt-3 text-sm leading-6 text-app-muted">将发送 SOL-USDT-SWAP 市价买入 1 张，cross 保证金模式。此按钮只允许模拟盘，不会走实盘。</p>
            {testOrderResult && (
              <div className={testOrderResult.ok ? "mt-4 rounded-xl border border-green-500/25 bg-green-500/10 p-3 text-sm text-success" : "mt-4 rounded-xl border border-red-500/25 bg-red-500/10 p-3 text-sm text-danger"}>
                <div>{testOrderResult.message}</div>
                <div className="mt-1 text-xs text-app-muted">订单号：{testOrderResult.response?.data?.[0]?.ordId || "-"}</div>
              </div>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setTestOrderOpen(false)}>关闭</Button>
              <Button variant="warn" onClick={placeTestOrder} disabled={testOrderBusy}>{testOrderBusy ? "下单中" : "确认下单"}</Button>
            </div>
          </Card>
        </div>
      )}

      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-5">
          <Card className="max-w-lg">
            <h3 className="text-xl font-semibold text-warning">确认启动模拟盘自动交易</h3>
            <p className="mt-3 text-sm leading-6 text-app-muted">系统将由 DeepSeek 判断行情，由策略生成信号，并由风控守卫自动审核。自动循环下单仍处于保守阶段；请先使用测试下单验证交易所侧链路。</p>
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

function Panel({ title, children }: PropsWithChildren<{ title: string }>) {
  return <div className="surface-soft scrollbar min-h-44 overflow-auto rounded-xl p-4 text-sm text-app-muted"><div className="mb-3 font-medium text-[var(--app-text)]">{title}</div>{children}</div>;
}

function StatusLine({ source, updatedAt, errors }: { source?: string; updatedAt?: string; errors?: string[] }) {
  return <div className="mb-3 space-y-1 text-xs"><div>来源：{source || "等待数据"} · 更新时间：{formatDate(updatedAt)}</div>{!!errors?.length && <div className="text-warning">提示：{errors.slice(0, 2).join("；")}</div>}</div>;
}

function MarketTable({ rows }: { rows: MarketRow[] }) {
  if (!rows.length) return <div className="rounded-lg border border-dashed border-[var(--app-line)] p-4">等待 OKX 真实行情。</div>;
  return (
    <div className="overflow-auto">
      <table className="w-full min-w-[640px] text-left text-xs">
        <thead className="text-app-muted"><tr><th className="py-2 pr-3">标的</th><th>最新价</th><th>24h</th><th>24h 成交额</th><th>Bid / Ask</th><th>更新时间</th></tr></thead>
        <tbody className="text-[var(--app-text)]">{rows.map((row) => <tr key={row.symbol} className="border-t border-[var(--app-line)]"><td className="py-2 pr-3 font-medium">{row.symbol}<div className="text-[11px] text-app-muted">{row.inst_id}</div></td><td>${formatNumber(row.last)}</td><td className={toneClass(row.change_24h_pct)}>{formatPct(row.change_24h_pct)}</td><td>${compactNumber(row.volume_24h)}</td><td>{formatNumber(row.bid)} / {formatNumber(row.ask)}</td><td className="text-app-muted">{formatDate(row.updated_at)}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

function OnchainTable({ rows }: { rows: OnchainRow[] }) {
  if (!rows.length) return <div className="rounded-lg border border-dashed border-[var(--app-line)] p-4">等待链上数据。</div>;
  return (
    <div className="overflow-auto">
      <table className="w-full min-w-[620px] text-left text-xs">
        <thead className="text-app-muted"><tr><th className="py-2 pr-3">资产 / 链</th><th>TVL</th><th>1d</th><th>7d</th><th>协议数</th><th>来源</th></tr></thead>
        <tbody className="text-[var(--app-text)]">{rows.map((row) => <tr key={row.chain} className="border-t border-[var(--app-line)]"><td className="py-2 pr-3 font-medium">{row.asset}<div className="text-[11px] text-app-muted">{row.raw_chain || row.chain}</div></td><td>${compactNumber(row.tvl)}</td><td className={toneClass(row.change_1d_pct)}>{formatPct(row.change_1d_pct)}</td><td className={toneClass(row.change_7d_pct)}>{formatPct(row.change_7d_pct)}</td><td>{formatNumber(row.protocols)}</td><td className="text-app-muted">{row.source}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

function AssetTable({ rows }: { rows: { ccy?: string; equity?: string; available?: string; frozen?: string; pnl?: string }[] }) {
  return (
    <div className="overflow-auto">
      <table className="w-full min-w-[520px] text-left text-xs">
        <thead className="text-app-muted"><tr><th className="py-2 pr-3">币种</th><th>权益/余额</th><th>可用</th><th>冻结</th><th>未实现盈亏</th></tr></thead>
        <tbody className="text-[var(--app-text)]">{rows.map((row) => <tr key={row.ccy} className="border-t border-[var(--app-line)]"><td className="py-2 pr-3 font-medium">{row.ccy || "-"}</td><td>{formatNumber(row.equity)}</td><td>{formatNumber(row.available)}</td><td>{formatNumber(row.frozen)}</td><td>{formatNumber(row.pnl)}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

function formatNumber(value?: number | string | null) {
  const numberValue = Number(value ?? 0);
  if (!Number.isFinite(numberValue)) return "--";
  return numberValue.toLocaleString("en-US", { maximumFractionDigits: 6 });
}

function compactNumber(value?: number | string | null) {
  const numberValue = Number(value ?? 0);
  if (!Number.isFinite(numberValue)) return "--";
  return Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(numberValue);
}

function formatPct(value?: number | string | null) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return "--";
  return `${numberValue >= 0 ? "+" : ""}${numberValue.toFixed(2)}%`;
}

function formatDate(value?: string) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function toneClass(value?: number | string | null) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return "";
  if (numberValue > 0) return "text-success";
  if (numberValue < 0) return "text-danger";
  return "";
}
