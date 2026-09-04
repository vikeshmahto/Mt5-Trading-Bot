import { Trade, Position, Zone, SystemStatus, LogEntry, Candle, SetupType, Session, Direction, Outcome } from "./types";
import { subDays, subHours, subMinutes, formatISO } from "date-fns";

// Seed generator for somewhat deterministic randomness
let seed = 12345;
function random() {
  const x = Math.sin(seed++) * 10000;
  return x - Math.floor(x);
}

// Generate Candles
export const generateCandles = (count: number, startPrice: number = 2000): Candle[] => {
  const candles: Candle[] = [];
  let currentPrice = startPrice;
  const now = new Date();
  
  for (let i = count; i > 0; i--) {
    const time = Math.floor(subMinutes(now, i * 15).getTime() / 1000); // 15m candles
    const volatility = currentPrice * 0.001;
    
    // Slight upward trend bias + random walk
    const change = (random() - 0.45) * volatility; 
    
    const open = currentPrice;
    const close = currentPrice + change;
    const high = Math.max(open, close) + random() * volatility;
    const low = Math.min(open, close) - random() * volatility;
    
    candles.push({ time, open, high, low, close });
    currentPrice = close;
  }
  
  return candles;
};

export const mockCandles = generateCandles(200, 2000); // Base mock dataset

// Generate Zones
export const mockZones: Zone[] = [
  {
    type: "orderblock",
    startTime: mockCandles[mockCandles.length - 50].time,
    endTime: mockCandles[mockCandles.length - 30].time,
    priceHigh: 2010.5,
    priceLow: 2008.0,
    timeframe: "M15"
  },
  {
    type: "fvg",
    startTime: mockCandles[mockCandles.length - 20].time,
    endTime: mockCandles[mockCandles.length - 5].time,
    priceHigh: 2025.0,
    priceLow: 2022.5,
    timeframe: "M15"
  }
];

// Generate Trades
const setupTypes: SetupType[] = ["OB+FVG confluence", "Liquidity Sweep", "BOS Breakout", "Trendline Bounce"];
const sessions: Session[] = ["asian", "london", "ny"];
const directions: Direction[] = ["long", "short"];

export const generateMockTrades = (count: number): Trade[] => {
  const trades: Trade[] = [];
  const now = new Date();
  
  for (let i = 0; i < count; i++) {
    const direction = directions[Math.floor(random() * directions.length)];
    const setupType = setupTypes[Math.floor(random() * setupTypes.length)];
    const session = sessions[Math.floor(random() * sessions.length)];
    
    const isWin = random() > 0.4; // 60% win rate
    const isBreakeven = !isWin && random() > 0.8; 
    
    const outcome: Outcome = isWin ? "win" : (isBreakeven ? "breakeven" : "loss");
    
    let rMultiple = 0;
    if (isWin) {
      rMultiple = 1 + random() * 3; // 1R to 4R wins
    } else if (isBreakeven) {
      rMultiple = 0;
    } else {
      rMultiple = -1; // -1R loss
    }
    
    const entryPrice = 2000 + (random() * 100 - 50);
    const slDist = entryPrice * 0.005;
    const sl = direction === "long" ? entryPrice - slDist : entryPrice + slDist;
    
    let exitPrice = entryPrice;
    if (isWin) {
      exitPrice = direction === "long" ? entryPrice + (slDist * rMultiple) : entryPrice - (slDist * rMultiple);
    } else if (!isBreakeven) {
      exitPrice = sl;
    }
    
    const tp = direction === "long" ? entryPrice + (slDist * 3) : entryPrice - (slDist * 3);
    
    const openedAt = subHours(now, (count - i) * 6);
    const closedAt = new Date(openedAt.getTime() + random() * 4 * 60 * 60 * 1000); // 0-4 hours later
    
    trades.push({
      id: `TRD-${1000 + i}`,
      symbol: "XAUUSD",
      direction,
      entryPrice: Number(entryPrice.toFixed(2)),
      exitPrice: Number(exitPrice.toFixed(2)),
      sl: Number(sl.toFixed(2)),
      tp: Number(tp.toFixed(2)),
      rMultiple: Number(rMultiple.toFixed(2)),
      outcome,
      setupType,
      session,
      openedAt: formatISO(openedAt),
      closedAt: formatISO(closedAt)
    });
  }
  return trades.reverse(); // Newest first
};

export const mockTrades = generateMockTrades(80);

// Open Positions
export const mockPositions: Position[] = [
  {
    id: "POS-1",
    symbol: "XAUUSD",
    direction: "long",
    entryPrice: 2020.5,
    currentPrice: 2025.2,
    sl: 2015.0,
    tp: 2035.0,
    floatingPnl: 470.0,
    openedAt: formatISO(subMinutes(new Date(), 45))
  },
  {
    id: "POS-2",
    symbol: "BTCUSD",
    direction: "short",
    entryPrice: 65000.0,
    currentPrice: 65150.0,
    sl: 66000.0,
    tp: 62000.0,
    floatingPnl: -150.0,
    openedAt: formatISO(subMinutes(new Date(), 120))
  }
];

export const mockSystemStatus: SystemStatus = {
  botStatus: "running",
  mt5Connected: true,
  regime: "trending",
  lastTickAt: formatISO(new Date())
};

export const mockLogs: LogEntry[] = [
  { id: "log-1", timestamp: formatISO(subMinutes(new Date(), 2)), level: "info", message: "Scanning XAUUSD M15 for OB+FVG confluence..." },
  { id: "log-2", timestamp: formatISO(subMinutes(new Date(), 5)), level: "success", message: "Closed XAUUSD Long at 2025.2 (+2.5R)" },
  { id: "log-3", timestamp: formatISO(subMinutes(new Date(), 15)), level: "warning", message: "Spread widened on BTCUSD during rollover" }
];
