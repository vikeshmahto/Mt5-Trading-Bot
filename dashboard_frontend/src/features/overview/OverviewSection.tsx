import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchPositions, fetchSystemStatus, fetchTrades, fetchConfig } from "@/lib/api";
import { ChartPanel } from "../chart/ChartPanel";
import { PositionsPanel } from "../positions/PositionsPanel";
import { LiveLogFeed } from "../live-log/LiveLogFeed";
import { Card, CardContent } from "@/components/ui/card";
import {
  DollarSign,
  Briefcase,
  TrendingUp,
  ShieldCheck,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";

interface OverviewSectionProps {
  onNavigate: (section: any) => void;
}

export function OverviewSection({ onNavigate }: OverviewSectionProps) {
  const { data: positions = [] } = useQuery({
    queryKey: ["positions"],
    queryFn: fetchPositions,
    refetchInterval: 2000,
  });

  const { data: status } = useQuery({
    queryKey: ["systemStatus"],
    queryFn: fetchSystemStatus,
    refetchInterval: 3000,
  });

  const { data: trades = [] } = useQuery({
    queryKey: ["trades"],
    queryFn: fetchTrades,
  });

  const { data: config } = useQuery({
    queryKey: ["riskConfig"],
    queryFn: fetchConfig,
  });

  const totalFloatingPnl = useMemo(() => {
    return positions.reduce((sum, p) => sum + (p.floatingPnl || 0), 0);
  }, [positions]);

  const winRate = useMemo(() => {
    if (!trades.length) return "0.0";
    const wins = trades.filter((t) => t.outcome === "win").length;
    return ((wins / trades.length) * 100).toFixed(1);
  }, [trades]);

  return (
    <div className="flex flex-col gap-6">
      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Floating P&L */}
        <Card className="bg-card/70 border-border/40 backdrop-blur-sm relative overflow-hidden group hover:border-emerald-500/30 transition-all">
          <div className="absolute top-0 right-0 p-3 opacity-10 group-hover:opacity-20 transition-opacity">
            <DollarSign className="h-16 w-16 text-emerald-400" />
          </div>
          <CardContent className="p-4 flex flex-col justify-between h-full">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Floating P&L
              </span>
              <span
                className={`flex items-center text-xs font-mono font-bold ${
                  totalFloatingPnl >= 0 ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {totalFloatingPnl >= 0 ? (
                  <ArrowUpRight className="h-3 w-3 mr-0.5" />
                ) : (
                  <ArrowDownRight className="h-3 w-3 mr-0.5" />
                )}
                {positions.length} Active
              </span>
            </div>
            <div className="mt-2">
              <div
                className={`text-2xl font-black font-mono tracking-tight ${
                  totalFloatingPnl >= 0 ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {totalFloatingPnl >= 0 ? "+" : ""}${totalFloatingPnl.toFixed(2)}
              </div>
              <span className="text-[11px] text-muted-foreground">
                Live unrealized open profit
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Active Positions */}
        <Card
          onClick={() => onNavigate("positions")}
          className="bg-card/70 border-border/40 backdrop-blur-sm relative overflow-hidden group hover:border-cyan-500/30 transition-all cursor-pointer"
        >
          <div className="absolute top-0 right-0 p-3 opacity-10 group-hover:opacity-20 transition-opacity">
            <Briefcase className="h-16 w-16 text-cyan-400" />
          </div>
          <CardContent className="p-4 flex flex-col justify-between h-full">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Open Orders
              </span>
              <span className="text-xs text-cyan-400 font-mono font-semibold">
                Manage →
              </span>
            </div>
            <div className="mt-2">
              <div className="text-2xl font-black text-foreground font-mono">
                {positions.length}
              </div>
              <span className="text-[11px] text-muted-foreground truncate">
                {positions.length > 0
                  ? `${positions[0].symbol} ${positions[0].direction.toUpperCase()}`
                  : "No open risk"}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Market Regime */}
        <Card
          onClick={() => onNavigate("chart")}
          className="bg-card/70 border-border/40 backdrop-blur-sm relative overflow-hidden group hover:border-purple-500/30 transition-all cursor-pointer"
        >
          <div className="absolute top-0 right-0 p-3 opacity-10 group-hover:opacity-20 transition-opacity">
            <TrendingUp className="h-16 w-16 text-purple-400" />
          </div>
          <CardContent className="p-4 flex flex-col justify-between h-full">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                SMC Market Regime
              </span>
              <span className="text-xs text-purple-400 font-mono font-semibold">
                Chart →
              </span>
            </div>
            <div className="mt-2">
              <div className="text-2xl font-black capitalize text-foreground">
                {status?.regime || "Scanning…"}
              </div>
              <span className="text-[11px] text-muted-foreground">
                ADX threshold filter active
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Risk & Safety */}
        <Card
          onClick={() => onNavigate("risk")}
          className="bg-card/70 border-border/40 backdrop-blur-sm relative overflow-hidden group hover:border-amber-500/30 transition-all cursor-pointer"
        >
          <div className="absolute top-0 right-0 p-3 opacity-10 group-hover:opacity-20 transition-opacity">
            <ShieldCheck className="h-16 w-16 text-amber-400" />
          </div>
          <CardContent className="p-4 flex flex-col justify-between h-full">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Risk Model
              </span>
              <span className="text-xs text-amber-400 font-mono font-semibold">
                Config →
              </span>
            </div>
            <div className="mt-2">
              <div className="text-2xl font-black text-foreground font-mono">
                {config?.riskPerTrade ?? 1.0}% <span className="text-xs text-muted-foreground font-normal">/ trade</span>
              </div>
              <span className="text-[11px] text-muted-foreground">
                Max loss: {config?.maxDailyLoss ?? 3.0}% | WinRate: {winRate}%
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Grid: Chart & Positions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 xl:grid-cols-4 gap-6 min-h-[460px]">
        <div className="col-span-1 lg:col-span-2 xl:col-span-3 h-[460px]">
          <ChartPanel />
        </div>
        <div className="col-span-1 lg:col-span-1 h-[460px] flex flex-col">
          <PositionsPanel />
        </div>
      </div>

      {/* Bottom Row: Live Console Log Feed */}
      <div className="grid grid-cols-1 gap-6 min-h-[320px]">
        <div className="h-[320px]">
          <LiveLogFeed />
        </div>
      </div>
    </div>
  );
}
