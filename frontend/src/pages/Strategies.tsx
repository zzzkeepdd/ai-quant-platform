import { ChevronDown } from "lucide-react";
import { useEffect } from "react";
import { usePlatformStore } from "../store/usePlatformStore";
import { Badge, Card } from "../components/ui";

export default function Strategies() {
  const { strategies, refresh } = usePlatformStore();
  useEffect(() => {
    refresh().catch(() => undefined);
  }, [refresh]);

  return (
    <div className="grid gap-5 xl:grid-cols-2">
      {strategies.map((strategy) => (
        <Card key={strategy.file}>
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">{strategy.name}</h2>
              <p className="mt-1 text-sm text-app-muted">{strategy.file}</p>
            </div>
            <div className="flex gap-2"><Badge tone="up">{strategy.score}</Badge><Badge>{strategy.market_state}</Badge></div>
          </div>
          <div className="space-y-2 text-sm">
            {Object.entries(strategy.tags).slice(0, 8).map(([key, value]) => (
              <div key={key} className="surface-soft rounded-xl p-3">
                <div className="text-xs text-app-muted">{key}</div>
                <div className="mt-1 text-[var(--app-text)]">{value}</div>
              </div>
            ))}
          </div>
          <details className="surface-soft mt-4 rounded-xl p-3">
            <summary className="flex cursor-pointer items-center gap-2 text-sm text-[var(--app-text)]"><ChevronDown size={16} />参数包</summary>
            <pre className="scrollbar mt-3 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-app-muted">{JSON.stringify(strategy.params, null, 2)}</pre>
          </details>
        </Card>
      ))}
    </div>
  );
}
