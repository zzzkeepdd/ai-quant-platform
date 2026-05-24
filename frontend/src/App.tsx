import { Activity, Bot, Brain, CandlestickChart, History, LayoutDashboard, Moon, Settings, Shield, Sparkles, Store, Sun } from "lucide-react";
import { NavLink, Route, Routes } from "react-router-dom";
import { useEffect, useState } from "react";
import { usePlatformStore } from "./store/usePlatformStore";
import Backtest from "./pages/Backtest";
import LiveMonitor from "./pages/LiveMonitor";
import Assistant from "./pages/Assistant";
import Optimizer from "./pages/Optimizer";
import Replay from "./pages/Replay";
import RiskPage from "./pages/Risk";
import Strategies from "./pages/Strategies";
import SettingsPage from "./pages/Settings";
import { Badge, Button } from "./components/ui";

const nav = [
  { to: "/", label: "策略回测", icon: CandlestickChart },
  { to: "/live", label: "实盘监控", icon: LayoutDashboard },
  { to: "/assistant", label: "AI助手", icon: Brain },
  { to: "/optimizer", label: "AI参数迭代", icon: Sparkles },
  { to: "/replay", label: "历史重放", icon: History },
  { to: "/risk", label: "风险管理", icon: Shield },
  { to: "/strategies", label: "策略管理", icon: Store },
  { to: "/settings", label: "系统设置", icon: Settings }
];

export default function App() {
  const { status, refresh } = usePlatformStore();
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("theme-light", theme === "light");
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    const onTheme = (event: Event) => {
      const next = (event as CustomEvent<string>).detail;
      if (next) setTheme(next);
    };
    window.addEventListener("platform-theme", onTheme);
    return () => window.removeEventListener("platform-theme", onTheme);
  }, []);

  useEffect(() => {
    refresh().catch(() => undefined);
    const id = window.setInterval(() => refresh().catch(() => undefined), 6000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const tradingRunning = status.trading?.running;
  const okxTone = status.okx?.connected ? "up" : status.okx?.configured ? "warn" : "warn";
  const okxText = status.okx?.display_state || (status.okx?.connected ? "已连接" : "未连接");
  const aiText = status.ai?.display_state || (status.ai?.connected ? "已连接" : "未配置");

  return (
    <div className="min-h-screen bg-[var(--app-bg)] text-[var(--app-text)]">
      <div className="flex min-h-screen">
        <aside className="hidden w-72 shrink-0 border-r border-[var(--app-line)] bg-[var(--app-sidebar)] p-5 lg:block">
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--app-button-bg)] text-[var(--app-button-text)]">
              <Bot size={22} />
            </div>
            <div>
              <div className="font-semibold">AI量化平台</div>
              <div className="text-xs text-app-muted">DeepSeek × OKX</div>
            </div>
          </div>
          <nav className="space-y-2">
            {nav.map((item) => (
              <NavLink key={item.to} to={item.to} className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${isActive ? "bg-[var(--app-nav-active-bg)] text-[var(--app-nav-active-text)]" : "text-app-muted hover:bg-[var(--app-hover)] hover:text-[var(--app-text)]"}`}>
                <item.icon size={18} />
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 border-b border-[var(--app-line)] bg-[var(--app-bg)]/80 px-5 py-4 backdrop-blur-xl">
            {tradingRunning && <div className="mb-3 rounded-xl border border-yellow-500/25 bg-yellow-500/10 px-4 py-2 text-sm text-warning">⚠️ 模拟盘自动交易运行中</div>}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h1 className="text-xl font-semibold">AI量化自动交易平台</h1>
                <p className="text-sm text-app-muted">行情理解、策略切换、风控审核、自动执行</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="ghost" className="h-9 px-3" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
                  {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
                  {theme === "dark" ? "浅色" : "深色"}
                </Button>
                <Badge tone={okxTone}>OKX {okxText}</Badge>
                <Badge tone={status.ai?.valid === false ? "down" : status.ai?.valid === true ? "up" : "warn"}>DeepSeek {aiText}</Badge>
                <Badge tone="neutral">市场 {status.trading?.market_state || "RANGING"}</Badge>
              </div>
            </div>
          </header>
          <div className="flex-1 p-5">
            <Routes>
              <Route path="/" element={<Backtest />} />
              <Route path="/live" element={<LiveMonitor />} />
              <Route path="/assistant" element={<Assistant />} />
              <Route path="/optimizer" element={<Optimizer />} />
              <Route path="/replay" element={<Replay />} />
              <Route path="/risk" element={<RiskPage />} />
              <Route path="/strategies" element={<Strategies />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </div>
          <footer className="border-t border-[var(--app-line)] px-5 py-3 text-xs text-app-muted">
            <div className="flex flex-wrap items-center gap-4">
              <span className="inline-flex items-center gap-1"><Activity size={14} />后端在线</span>
              <span className="inline-flex items-center gap-1"><Shield size={14} />杠杆上限 {String(status.risk?.rules?.max_leverage ?? 3)}x / 日亏损熔断 {Number(status.risk?.rules?.daily_loss_circuit_breaker ?? 0.05) * 100}%</span>
              <span>模式：{status.trading?.mode || "sandbox"}</span>
              <span>连续失败：{status.trading?.consecutive_failures ?? 0}</span>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}
