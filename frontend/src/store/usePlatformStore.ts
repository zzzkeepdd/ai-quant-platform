import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api, StrategyInfo } from "../lib/api";

type PlatformStatus = {
  okx?: { connected: boolean; configured?: boolean; auth_ok?: boolean; display_state?: string; state?: string; mode: string; last_error?: string | null; data_warnings?: string[] };
  ai?: { connected: boolean; configured?: boolean; valid?: boolean | null; last_error?: string | null; display_state?: string };
  trading?: {
    running: boolean;
    mode: string;
    market_state: string;
    consecutive_failures: number;
    active_strategies?: Record<string, Record<string, unknown>>;
    last_iterations?: Record<string, Record<string, unknown>>;
  };
  risk?: { rules: Record<string, unknown> };
};

type PlatformState = {
  status: PlatformStatus;
  strategies: StrategyInfo[];
  logs: string[];
  pageState: Record<string, unknown>;
  refresh: () => Promise<void>;
  pushLog: (line: string) => void;
  setPageState: <T>(key: string, value: T) => void;
};

export const usePlatformStore = create<PlatformState>()(
  persist(
    (set, get) => ({
      status: {},
      strategies: [],
      logs: [],
      pageState: {},
      refresh: async () => {
        const [status, strategies] = await Promise.all([
          api<PlatformStatus>("/api/status"),
          api<StrategyInfo[]>("/api/strategies")
        ]);
        set({ status, strategies });
      },
      pushLog: (line) => set({ logs: [line, ...get().logs].slice(0, 200) }),
      setPageState: (key, value) => set({ pageState: { ...get().pageState, [key]: value } })
    }),
    {
      name: "ai-quant-platform-ui",
      partialize: (state) => ({ pageState: state.pageState, logs: state.logs.slice(0, 50) })
    }
  )
);
