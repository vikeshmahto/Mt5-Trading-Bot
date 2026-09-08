export type SetupType = "OB+FVG confluence" | "Liquidity Sweep" | "BOS Breakout" | "Trendline Bounce";
export type Session = "asian" | "london" | "ny";
export type Direction = "long" | "short";
export type Outcome = "win" | "loss" | "breakeven";

export interface Trade {
  id: string;
  symbol: string;
  direction: Direction;
  entryPrice: number;
  exitPrice?: number | null;
  sl: number;
  tp: number;
  rMultiple?: number | null;
  outcome?: Outcome | null;
  setupType: string;
  session: Session;
  openedAt: string;
  closedAt?: string | null;
  source?: "paper" | "backtest" | "live" | "manual_note";

  // 1. Context / Bias
  htfBias?: "bullish" | "bearish" | "range" | null;
  htfReason?: string | null;
  biasCorrect?: "yes" | "no" | "partial" | null;

  // 2. Setup
  setupTimeframe?: string | null;
  confluence?: string | null;
  screenshotUrl?: string | null;

  // 3. Execution
  entryTimeframe?: string | null;
  entryTrigger?: string | null;
  slLogic?: string | null;
  plannedRr?: number | null;
  riskPct?: number | null;

  // 4. Outcome & Excursion
  pointsCaptured?: number | null;
  mae?: number | null;
  mfe?: number | null;

  // 5. Process / Psychology
  ruleAdherence?: string | null;
  emotionalState?: string | null;
  externalFactor?: string | null;

  // 6. Post-Trade Review & Mistake Taxonomy
  textbookComparison?: string | null;
  mistakeType?: string | null;
  reviewNotes?: string | null;
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
