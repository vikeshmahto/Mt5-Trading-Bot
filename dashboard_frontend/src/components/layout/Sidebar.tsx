import React from "react";
import {
  LayoutDashboard,
  CandlestickChart,
  Briefcase,
  TrendingUp,
  BookOpen,
  Sliders,
  Terminal,
  ChevronLeft,
  ChevronRight,
  Zap,
  ShieldCheck,
  Server
} from "lucide-react";
import { Button } from "@/components/ui/button";

export type NavSection =
  | "overview"
  | "chart"
  | "positions"
  | "analytics"
  | "journal"
  | "risk"
  | "logs";

interface SidebarProps {
  currentSection: NavSection;
  onSelectSection: (section: NavSection) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  activePositionsCount: number;
  mt5Connected: boolean;
  botStatus: "running" | "paused" | "stopped";
}

export function Sidebar({
  currentSection,
  onSelectSection,
  collapsed,
  onToggleCollapse,
  activePositionsCount,
  mt5Connected,
  botStatus: _botStatus
}: SidebarProps) {
  const navItems = [
    {
      id: "overview" as NavSection,
      label: "Overview",
      icon: LayoutDashboard,
      badge: null,
    },
    {
      id: "chart" as NavSection,
      label: "Live SMC Chart",
      icon: CandlestickChart,
      badge: "M15",
    },
    {
      id: "positions" as NavSection,
      label: "Open Positions",
      icon: Briefcase,
      badge: activePositionsCount > 0 ? `${activePositionsCount}` : null,
    },
    {
      id: "analytics" as NavSection,
      label: "Performance",
      icon: TrendingUp,
      badge: null,
    },
    {
      id: "journal" as NavSection,
      label: "Trade Journal",
      icon: BookOpen,
      badge: null,
    },
    {
      id: "risk" as NavSection,
      label: "Risk & Setups",
      icon: Sliders,
      badge: null,
    },
    {
      id: "logs" as NavSection,
      label: "System Console",
      icon: Terminal,
      badge: "Live",
    },
  ];

  return (
    <aside
      className={`relative flex flex-col border-r border-border/40 bg-card/60 backdrop-blur-xl transition-all duration-300 ease-in-out shrink-0 z-30 ${
        collapsed ? "w-16" : "w-64"
      }`}
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between px-3.5 border-b border-border/40">
        {!collapsed && (
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-500/20 text-black font-black text-lg shrink-0">
              <Zap className="h-5 w-5 fill-black text-black" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="font-black text-sm tracking-tight text-foreground uppercase">
                  SMC QUANT
                </span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  PRO
                </span>
              </div>
              <span className="text-[11px] text-muted-foreground font-mono">
                XAUUSD / BTCUSD
              </span>
            </div>
          </div>
        )}

        {collapsed && (
          <div className="mx-auto h-9 w-9 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg text-black font-black">
            <Zap className="h-5 w-5 fill-black text-black" />
          </div>
        )}

        {/* Collapse Toggle Button */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleCollapse}
          className={`h-7 w-7 text-muted-foreground hover:text-foreground ${
            collapsed ? "hidden" : "flex"
          }`}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        <div className="px-2 mb-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
          {!collapsed ? "Trading System" : "Menu"}
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentSection === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectSection(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group relative ${
                isActive
                  ? "bg-emerald-500/15 text-emerald-400 font-semibold shadow-sm shadow-emerald-500/10 border border-emerald-500/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-white/5"
              }`}
              title={collapsed ? item.label : undefined}
            >
              <Icon
                className={`h-4 w-4 shrink-0 transition-transform duration-200 group-hover:scale-110 ${
                  isActive ? "text-emerald-400" : "text-muted-foreground"
                }`}
              />

              {!collapsed && (
                <span className="flex-1 text-left truncate">{item.label}</span>
              )}

              {!collapsed && item.badge && (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold ${
                    item.id === "positions" && activePositionsCount > 0
                      ? "bg-emerald-500 text-black animate-pulse"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {item.badge}
                </span>
              )}

              {/* Collapsed active dot */}
              {collapsed && isActive && (
                <div className="absolute right-1 h-2 w-2 rounded-full bg-emerald-400" />
              )}
            </button>
          );
        })}
      </div>

      {/* Bottom Collapsed Toggle if collapsed */}
      {collapsed && (
        <div className="p-2 border-t border-border/40 flex justify-center">
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleCollapse}
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            title="Expand sidebar"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Bottom Account & Connection Footer */}
      {!collapsed && (
        <div className="p-3 border-t border-border/40 bg-card/40 flex flex-col gap-2.5">
          <div className="p-2.5 rounded-lg bg-black/40 border border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2 overflow-hidden">
              <Server className="h-4 w-4 text-cyan-400 shrink-0" />
              <div className="flex flex-col truncate">
                <span className="text-xs font-semibold text-foreground truncate">
                  VantageMarkets-Demo
                </span>
                <span className="text-[10px] text-muted-foreground font-mono">
                  #25989443
                </span>
              </div>
            </div>
            <div
              className={`h-2.5 w-2.5 rounded-full ${
                mt5Connected ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse" : "bg-red-500"
              }`}
              title={mt5Connected ? "MT5 Live & Connected" : "MT5 Disconnected"}
            />
          </div>

          <div className="flex items-center justify-between px-1 text-[11px] text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              Safe Risk Guard
            </span>
            <span className="font-mono text-foreground font-semibold">1.0%</span>
          </div>
        </div>
      )}
    </aside>
  );
}
