import { useEffect, useState } from "react";
import { Download, KeyRound, Moon, PlugZap, Save, Sun } from "lucide-react";
import { api } from "../lib/api";
import { usePlatformStore } from "../store/usePlatformStore";
import { Button, Card, Input, Select } from "../components/ui";

export default function SettingsPage() {
  const { status, refresh } = usePlatformStore();
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark");
  const [form, setForm] = useState({
    okx_api_key: "",
    okx_secret_key: "",
    okx_password: "",
    deepseek_api_key: "",
    proxy_type: "http",
    proxy_host: "127.0.0.1",
    proxy_port: 7897,
    market_mode: "sandbox"
  });
  const [secretState, setSecretState] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState("");
  const [diagnosis, setDiagnosis] = useState<Record<string, unknown> | null>(null);
  const [aiDiagnosis, setAiDiagnosis] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    api<{ proxy: { type: string; host: string; port: number }; market_mode: string; secrets: Record<string, boolean> }>("/api/settings")
      .then((settings) => {
        setForm((old) => ({
          ...old,
          proxy_type: settings.proxy?.type || old.proxy_type,
          proxy_host: settings.proxy?.host || old.proxy_host,
          proxy_port: settings.proxy?.port || old.proxy_port,
          market_mode: settings.market_mode || old.market_mode
        }));
        setSecretState(settings.secrets || {});
      })
      .catch(() => undefined);
  }, []);

  function update(key: string, value: string | number) {
    setForm((old) => ({ ...old, [key]: value }));
  }

  function changeTheme(next: string) {
    setTheme(next);
    localStorage.setItem("theme", next);
    window.dispatchEvent(new CustomEvent("platform-theme", { detail: next }));
  }

  async function save() {
    const result = await api<{ message: string }>("/api/settings/secrets", { method: "POST", body: JSON.stringify(form) });
    setMessage(result.message);
    setForm((old) => ({ ...old, okx_api_key: "", okx_secret_key: "", okx_password: "", deepseek_api_key: "" }));
    await refresh();
    const settings = await api<{ secrets: Record<string, boolean> }>("/api/settings");
    setSecretState(settings.secrets || {});
  }

  async function test() {
    const result = await api<{ message: string; diagnosis: Record<string, unknown> }>("/api/exchange/test", { method: "POST" });
    setMessage(result.message);
    setDiagnosis(result.diagnosis || null);
    await refresh();
  }

  async function diagnose() {
    const result = await api<Record<string, unknown>>("/api/exchange/diagnose");
    setDiagnosis(result);
    setMessage(String(result.recommended_action || "OKX诊断完成"));
    await refresh();
  }

  async function diagnoseAi() {
    const result = await api<Record<string, unknown>>("/api/ai/diagnose");
    setAiDiagnosis(result);
    setMessage(`DeepSeek：${String(result.display_state || "诊断完成")}`);
    await refresh();
  }

  function exportLog(type: "trade" | "ai" | "system") {
    window.open(`/api/logs/export?type=${type}`, "_blank");
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
      <Card>
        <h2 className="flex items-center gap-2 text-lg font-semibold"><KeyRound size={20} />连接配置</h2>
        <p className="mt-1 text-sm text-app-muted">密钥会加密保存到本地SQLite，不写入源码或日志。保存后顶部状态会自动刷新。</p>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <Input placeholder="OKX API Key" value={form.okx_api_key} onChange={(e) => update("okx_api_key", e.target.value)} />
          <Input placeholder="OKX Secret Key" type="password" value={form.okx_secret_key} onChange={(e) => update("okx_secret_key", e.target.value)} />
          <Input placeholder="OKX Passphrase" type="password" value={form.okx_password} onChange={(e) => update("okx_password", e.target.value)} />
          <Input placeholder="DeepSeek API Key" type="password" value={form.deepseek_api_key} onChange={(e) => update("deepseek_api_key", e.target.value)} />
          <Select value={form.proxy_type} onChange={(e) => update("proxy_type", e.target.value)}>
            <option value="http">HTTP代理</option>
            <option value="socks5">SOCKS5代理</option>
            <option value="none">不使用代理</option>
          </Select>
          <Select value={form.market_mode} onChange={(e) => update("market_mode", e.target.value)}>
            <option value="sandbox">OKX模拟盘</option>
            <option value="live">OKX实盘</option>
          </Select>
          <Input placeholder="代理地址" value={form.proxy_host} onChange={(e) => update("proxy_host", e.target.value)} />
          <Input placeholder="代理端口" type="number" value={form.proxy_port} onChange={(e) => update("proxy_port", Number(e.target.value))} />
        </div>
        <div className="mt-4 grid gap-2 text-sm text-app-muted md:grid-cols-2">
          <div>OKX API Key：{secretState.okx_api_key ? "已配置" : "未配置"}</div>
          <div>OKX Secret：{secretState.okx_secret_key ? "已配置" : "未配置"}</div>
          <div>OKX Passphrase：{secretState.okx_password ? "已配置" : "未配置"}</div>
          <div>DeepSeek：{secretState.deepseek_api_key ? "已配置" : "未配置"}</div>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          <Button onClick={save}><Save size={16} />保存配置</Button>
          <Button variant="ghost" onClick={test}><PlugZap size={16} />测试OKX连接</Button>
          <Button variant="ghost" onClick={diagnose}><PlugZap size={16} />一键诊断OKX</Button>
          <Button variant="ghost" onClick={diagnoseAi}><PlugZap size={16} />测试DeepSeek</Button>
        </div>
        {message && <div className="surface-soft mt-4 rounded-xl p-3 text-sm">{message}</div>}
        {diagnosis && (
          <div className="surface-soft mt-4 rounded-xl p-3 text-sm">
            <div className="mb-2 font-medium">OKX诊断结果</div>
            <pre className="scrollbar max-h-72 overflow-auto whitespace-pre-wrap text-xs text-app-muted">{JSON.stringify(diagnosis, null, 2)}</pre>
          </div>
        )}
        {aiDiagnosis && (
          <div className="surface-soft mt-4 rounded-xl p-3 text-sm">
            <div className="mb-2 font-medium">DeepSeek诊断结果</div>
            <pre className="scrollbar max-h-48 overflow-auto whitespace-pre-wrap text-xs text-app-muted">{JSON.stringify(aiDiagnosis, null, 2)}</pre>
          </div>
        )}
      </Card>
      <div className="space-y-5">
        <Card>
          <h2 className="text-lg font-semibold">界面主题</h2>
          <p className="mt-1 text-sm text-app-muted">可在深色和浅色管理界面之间切换。</p>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Button variant={theme === "dark" ? "primary" : "ghost"} onClick={() => changeTheme("dark")}><Moon size={16} />深色</Button>
            <Button variant={theme === "light" ? "primary" : "ghost"} onClick={() => changeTheme("light")}><Sun size={16} />浅色</Button>
          </div>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold">风控规则</h2>
          <pre className="mt-3 whitespace-pre-wrap text-xs text-app-muted">{JSON.stringify(status.risk?.rules || {}, null, 2)}</pre>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold">日志管理</h2>
          <div className="mt-4 grid gap-2">
            <Button variant="ghost" onClick={() => exportLog("trade")}><Download size={16} />导出交易日志</Button>
            <Button variant="ghost" onClick={() => exportLog("ai")}><Download size={16} />导出AI日志</Button>
            <Button variant="ghost" onClick={() => exportLog("system")}><Download size={16} />导出系统日志</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
