import { useState } from "react";
import { Brain, Send } from "lucide-react";
import { api, wsUrl } from "../lib/api";
import { usePlatformStore } from "../store/usePlatformStore";
import { Button, Card, Input, Select, Textarea } from "../components/ui";

type AssistantState = {
  symbol: string;
  initialCapital: number;
  summary: string;
  analysisOutput: string;
};

const defaults: AssistantState = {
  symbol: "ALL",
  initialCapital: 10000,
  summary: "请根据OKX最新K线和当前账户状态分析行情。",
  analysisOutput: ""
};

export default function Assistant() {
  const { pageState, setPageState } = usePlatformStore();
  const cached = { ...defaults, ...((pageState.assistant as Partial<AssistantState>) || {}) };
  const [symbol, setSymbolValue] = useState(cached.symbol);
  const [initialCapital, setInitialCapitalValue] = useState(cached.initialCapital);
  const [summary, setSummaryValue] = useState(cached.summary);
  const [analysisOutput, setAnalysisOutputValue] = useState(cached.analysisOutput || (cached as { output?: string }).output || "");
  const [streaming, setStreaming] = useState(false);

  function cache(next: Partial<AssistantState>) {
    setPageState("assistant", { symbol, initialCapital, summary, analysisOutput, ...next });
  }

  function setSymbol(next: string) {
    setSymbolValue(next);
    cache({ symbol: next });
  }

  function setInitialCapital(next: number) {
    setInitialCapitalValue(next);
    cache({ initialCapital: next });
  }

  function setSummary(next: string) {
    setSummaryValue(next);
    cache({ summary: next });
  }

  function setAnalysisOutput(next: string) {
    setAnalysisOutputValue(next);
    cache({ analysisOutput: next });
  }

  async function runAnalysis() {
    let nextOutput = "";
    setAnalysisOutput(nextOutput);
    setStreaming(true);
    const data = await api<{ ws: string }>("/api/ai/analyze", {
      method: "POST",
      body: JSON.stringify({ symbol, timeframe: "15m", initial_capital: initialCapital, market_summary: summary })
    });
    const ws = new WebSocket(wsUrl(data.ws));
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.delta) {
        nextOutput += msg.delta;
        setAnalysisOutputValue(nextOutput);
        setPageState("assistant", { symbol, initialCapital, summary, analysisOutput: nextOutput });
      }
      if (msg.done) {
        setStreaming(false);
        ws.close();
      }
    };
    ws.onerror = () => setStreaming(false);
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[390px_1fr]">
      <Card>
        <h2 className="flex items-center gap-2 text-lg font-semibold"><Brain size={20} />AI助手</h2>
        <p className="mt-1 text-sm text-app-muted">这里只做OKX最新行情分析；参数迭代已经移到左侧“AI参数迭代”。</p>
        <div className="mt-5 space-y-4">
          <Select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
            <option value="ALL">BTC + ETH + SOL 三币种</option>
            <option>BTC/USDT:USDT</option>
            <option>ETH/USDT:USDT</option>
            <option>SOL/USDT:USDT</option>
          </Select>
          <label className="block text-sm text-app-muted">参考本金<Input className="mt-2" type="number" value={initialCapital} onChange={(event) => setInitialCapital(Number(event.target.value))} /></label>
          <div className="surface-soft rounded-xl p-3 text-sm text-app-muted">行情分析只解释市场结构、趋势/震荡/高波动状态、风险证据和当前不适合交易的原因，不在这里跑参数网格。</div>
          <Textarea value={summary} onChange={(event) => setSummary(event.target.value)} />
          <Button className="w-full" onClick={runAnalysis} disabled={streaming}><Send size={16} />{streaming ? "分析中" : "行情分析"}</Button>
        </div>
      </Card>
      <Card>
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold"><Send size={18} />行情分析</h2>
        <div className="scrollbar min-h-[420px] whitespace-pre-wrap rounded-xl border border-[var(--app-line)] bg-[var(--app-soft)] p-4 text-sm leading-7">
          {analysisOutput || "等待行情分析输出。"}
        </div>
      </Card>
    </div>
  );
}
