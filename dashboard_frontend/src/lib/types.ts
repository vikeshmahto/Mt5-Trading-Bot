export type SetupType = "OB+FVG confluence" | "Liquidity Sweep" | "BOS Breakout" | "Trendline Bounce";
export type Session = "asian" | "london" | "ny";
export type Direction = "long" | "short";
export type Outcome = "win" | "loss" | "breakeven";

export interface Trade {
  id: string;
  symbol: string;
  direction: Direction;
  entryPrice: number;
  exitPrice: number;
  sl: number;
  tp: number;
  rMultiple: number;
  outcome: Outcome;
  setupType: string;
  session: Session;
  openedAt: string;
  closedAt: string;
}

export interface Position {
  id: string;
  symbol: string;
  direction: Direction;
  entryPrice: number;
  currentPrice: number;
  sl: number;
  tp: number;
  floatingPnl: number;
  openedAt: string;
}

export interface Zone {
  type: "orderblock" | "fvg" | "liquidity-sweep";
  startTime: number;
  endTime: number;
  priceHigh: number;
  priceLow: number;
  timeframe: string;
}

export interface SystemStatus {
  botStatus: "running" | "paused" | "stopped";
  mt5Connected: boolean;
  regime: "trending" | "ranging";
  lastTickAt: string;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: "info" | "warning" | "error" | "success";
  message: string;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}
