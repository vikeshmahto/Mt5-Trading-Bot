import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchSystemStatus, pauseBot, resumeBot, forceSignal } from "@/lib/api";
import { NavSection } from "./Sidebar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Menu,
  Play,
  Pause,
  RefreshCw,
  Globe,
  TrendingUp,
  Radio,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

interface TopNavProps {
  currentSection: NavSection;
  onToggleMobileSidebar?: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

const sectionTitles: Record<NavSection, { title: string; subtitle: string }> = {
  overview: {
    title: "Executive Overview",
    subtitle: "Real-time market snapshot & order status",
  },
  chart: {
    title: "Live SMC Candlestick Chart",
    subtitle: "Multi-timeframe Order Blocks & Fair Value Gaps",
  },
  positions: {
    title: "Open Positions Manager",
    subtitle: "Active MT5 market deals and live floating P&L",
  },
  analytics: {
    title: "Performance & Quant Analytics",
    subtitle: "Equity curve, win rate by setup, and R-multiples",
  },
  journal: {
    title: "Trade Execution Journal",
    subtitle: "Audited historical trade log with session tags",
  },
  risk: {
    title: "Risk & Strategy Configuration",
    subtitle: "Dynamic position sizing, circuit breakers & SMC setups",
  },
  logs: {
    title: "Real-Time System Console",
    subtitle: "WebSocket streaming audit trail & engine telemetry",
  },
};

export function TopNav({
  currentSection,
  onToggleCollapse,
  collapsed,
}: TopNavProps) {
  const queryClient = useQueryClient();

  const [liveTick, setLiveTick] = useState<{
    symbol: string;
    bid: number;
    ask: number;
  } | null>(null);

  // Subscribe to live tick via WebSocket
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: any;

    const connect = () => {
      try {
        ws = new WebSocket("ws://localhost:8000/ws/live");
        ws.onmessage = (event) => {
          try {
            const parsed = JSON.parse(event.data);
            if (parsed.type === "tick" && parsed.data) {
              setLiveTick({
                symbol: parsed.data.symbol,
                bid: parsed.data.bid,
                ask: parsed.data.ask,
              });
            }
          } catch {
            // Ignore non-json
          }
        };
        ws.onclose = () => {
          reconnectTimeout = setTimeout(connect, 4000);
        };
      } catch {
        reconnectTimeout = setTimeout(connect, 4000);
      }
    };

    connect();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, []);

  const {
    data: status = {
      botStatus: "running",
      mt5Connected: false,
      regime: "ranging",
    },
  } = useQuery({
    queryKey: ["systemStatus"],
    queryFn: fetchSystemStatus,
    refetchInterval: 3000,
  });

  const toggleMutation = useMutation({
    mutationFn: async () => {
      if (status.botStatus === "running") {
        return await pauseBot();
      } else {
        return await resumeBot();
      }
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["systemStatus"] });
      toast.info(`Bot status updated to ${res.botStatus.toUpperCase()}`);
    },
    onError: (err: any) => {
      toast.error(`Control action failed: ${err.message}`);
    },
  });

  const forceSignalMutation = useMutation({
    mutationFn: forceSignal,
    onSuccess: () => {
      toast.success("Signal loop triggered manually", {
        description: "Checking M15 SMC setups on active symbols...",
      });
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["logs"] });
    },
    onError: (err: any) => {
      toast.error(`Force scan failed: ${err.message}`);
    },
  });

  const { title, subtitle } = sectionTitles[currentSection];

  return (
    <header className="h-16 border-b border-border/40 bg-card/60 backdrop-blur-xl px-4 md:px-6 flex items-center justify-between gap-4 z-20 shrink-0">
      {/* Left: Collapse Toggle & Section Title */}
      <div className="flex items-center gap-3">
        {collapsed && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleCollapse}
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
          >
            <Menu className="h-4 w-4" />
          </Button>
        )}
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <h1 className="text-base md:text-lg font-bold tracking-tight text-foreground">
              {title}
            </h1>
          </div>
          <p className="text-xs text-muted-foreground hidden sm:block">
            {subtitle}
          </p>
        </div>
      </div>

      {/* Right: Live Ticker, Status Badges, and Action Buttons */}
      <div className="flex items-center gap-2.5 md:gap-3.5">
        {/* Live Ticker Box */}
        {liveTick && (
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-lg bg-black/40 border border-border/30 font-mono text-xs">
            <Radio className="h-3 w-3 text-emerald-400 animate-pulse" />
            <span className="font-bold text-foreground">{liveTick.symbol}</span>
            <span className="text-emerald-400 font-semibold">
              ${liveTick.bid.toFixed(2)}
            </span>
            <span className="text-muted-foreground text-[10px]">
              / ${(liveTick.ask - liveTick.bid).toFixed(2)} sp
            </span>
          </div>
        )}

        {/* Market Regime Badge */}
        <Badge
          variant="outline"
          className="hidden md:flex items-center gap-1 text-xs py-1 px-2.5 border-border/40 bg-background/50"
        >
          <TrendingUp className="h-3 w-3 text-cyan-400" />
          <span className="capitalize">{status.regime}</span>
        </Badge>

        {/* MT5 Connection Pill */}
        <div
          className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border transition-all ${
            status.mt5Connected
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              : "bg-red-500/10 border-red-500/30 text-red-400"
          }`}
        >
          <Globe
            className={`h-3.5 w-3.5 ${
              status.mt5Connected ? "text-emerald-400" : "text-red-400"
            }`}
          />
          <span className="hidden sm:inline font-medium">
            {status.mt5Connected ? "MT5 Connected" : "MT5 Offline"}
          </span>
        </div>

        {/* Force Scan Button */}
        <Button
          variant="outline"
          size="sm"
          disabled={forceSignalMutation.isPending || !status.mt5Connected}
          onClick={() => forceSignalMutation.mutate()}
          className="h-8 px-2.5 text-xs gap-1.5 border-border/40 hover:bg-white/5"
          title="Manually trigger signal scanner loop"
        >
          <Zap
            className={`h-3.5 w-3.5 text-yellow-400 ${
              forceSignalMutation.isPending ? "animate-spin" : ""
            }`}
          />
          <span className="hidden md:inline">Scan Now</span>
        </Button>

        {/* Pause / Resume Button */}
        <Button
          variant={status.botStatus === "running" ? "outline" : "default"}
          size="sm"
          disabled={toggleMutation.isPending}
          onClick={() => toggleMutation.mutate()}
          className={`h-8 px-3 text-xs gap-1.5 shadow-sm font-semibold transition-all ${
            status.botStatus === "running"
              ? "border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
              : "bg-emerald-500 text-black hover:bg-emerald-400"
          }`}
        >
          {status.botStatus === "running" ? (
            <>
              <Pause className="h-3.5 w-3.5" />
              <span>Pause Bot</span>
            </>
          ) : (
            <>
              <Play className="h-3.5 w-3.5 fill-black" />
              <span>Resume Bot</span>
            </>
          )}
        </Button>
      </div>
    </header>
  );
}
