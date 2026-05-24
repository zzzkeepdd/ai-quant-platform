import { useEffect, useState } from "react";
import { Save, ShieldCheck } from "lucide-react";
import { api } from "../lib/api";
import { usePlatformStore } from "../store/usePlatformStore";
import { Button, Card, Input, Metric } from "../components/ui";

type RiskRules = {
  principal_usdt: number;
  max_leverage: number;
  risk_per_trade: number;
  daily_loss_circuit_breaker: number;
  atr_circuit_breaker_mult: number;
  min_notional_usdt: number;
  strategy_cooldown_hours: number;
  max_consecutive_order_failures: number;
};

const defaults: RiskRules = {
  principal_usdt: 10000,
  max_leverage: 3,
  risk_per_trade: 0.01,
  daily_loss_circuit_breaker: 0.05,
  atr_circuit_breaker_mult: 3.5,
  min_notional_usdt: 10,
  strategy_cooldown_hours: 12,
  max_consecutive_order_failures: 3
};

export default function RiskPage() {
  const { refresh } = usePlatformStore();
  const [rules, setRules] = useState<RiskRules>(defaults);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<{ rules: RiskRules }>("/api/risk").then((data) => setRules({ ...defaults, ...data.rules })).catch(() => undefined);
  }, []);

  function update(key: keyof RiskRules, value: number) {
    setRules((old) => ({ ...old, [key]: value }));
  }

  async function save() {
    const result = await api<{ message: string; rules: RiskRules }>("/api/risk", { method: "POST", body: JSON.stringify(rules) });
    setRules(result.rules);
    setMessage(result.message);
    await refresh();
  }

  const riskAmount = rules.principal_usdt * rules.risk_per_trade;

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold"><ShieldCheck size={20} />风险管理</h2>
            <p className="mt-1 text-sm text-app-muted">这些规则会被模拟自动交易、实盘建议和订单审核共同读取。</p>
          </div>
          <Button onClick={save}><Save size={16} />保存规则</Button>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="text-sm text-app-muted">本金 USDT<Input className="mt-2" type="number" value={rules.principal_usdt} onChange={(e) => update("principal_usdt", Number(e.target.value))} /></label>
          <label className="text-sm text-app-muted">最大杠杆<Input className="mt-2" type="number" value={rules.max_leverage} onChange={(e) => update("max_leverage", Number(e.target.value))} /></label>
          <label className="text-sm text-app-muted">
            单笔最大可接受亏损比例
            <Input className="mt-2" type="number" step="0.001" value={rules.risk_per_trade} onChange={(e) => update("risk_per_trade", Number(e.target.value))} />
            <span className="mt-1 block text-xs">例如 0.01 = 单笔最多亏本金 1%</span>
          </label>
          <label className="text-sm text-app-muted">日亏损熔断<Input className="mt-2" type="number" step="0.001" value={rules.daily_loss_circuit_breaker} onChange={(e) => update("daily_loss_circuit_breaker", Number(e.target.value))} /></label>
          <label className="text-sm text-app-muted">ATR熔断倍数<Input className="mt-2" type="number" step="0.1" value={rules.atr_circuit_breaker_mult} onChange={(e) => update("atr_circuit_breaker_mult", Number(e.target.value))} /></label>
          <label className="text-sm text-app-muted">最小名义仓位<Input className="mt-2" type="number" value={rules.min_notional_usdt} onChange={(e) => update("min_notional_usdt", Number(e.target.value))} /></label>
          <label className="text-sm text-app-muted">策略冷却小时<Input className="mt-2" type="number" value={rules.strategy_cooldown_hours} onChange={(e) => update("strategy_cooldown_hours", Number(e.target.value))} /></label>
          <label className="text-sm text-app-muted">连续失败暂停<Input className="mt-2" type="number" value={rules.max_consecutive_order_failures} onChange={(e) => update("max_consecutive_order_failures", Number(e.target.value))} /></label>
        </div>
        {message && <div className="surface-soft mt-4 rounded-xl p-3 text-sm">{message}</div>}
      </Card>
      <div className="grid gap-4 md:grid-cols-4">
        <Metric label="账户本金" value={`${rules.principal_usdt}`} />
        <Metric label="单笔最大可接受亏损" value={`${riskAmount.toFixed(2)} USDT`} tone="warn" />
        <Metric label="杠杆上限" value={`${rules.max_leverage}x`} />
        <Metric label="日亏损熔断" value={`${(rules.daily_loss_circuit_breaker * 100).toFixed(1)}%`} tone="down" />
      </div>
    </div>
  );
}
