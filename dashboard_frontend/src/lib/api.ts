import { Trade, Position, SystemStatus, Candle, Zone } from "./types";

const API_BASE = "http://localhost:8000/api";

export const fetchSystemStatus = async (): Promise<SystemStatus> => {
  const res = await fetch(`${API_BASE}/status`);
  if (!res.ok) throw new Error("Failed to fetch system status");
  return res.json();
};

export const fetchPositions = async (): Promise<Position[]> => {
  const res = await fetch(`${API_BASE}/positions`);
  if (!res.ok) throw new Error("Failed to fetch positions");
  return res.json();
};

export const fetchTrades = async (): Promise<Trade[]> => {
  const res = await fetch(`${API_BASE}/trades`);
  if (!res.ok) throw new Error("Failed to fetch trades");
  return res.json();
};

export const fetchChartData = async (symbol: string, timeframe: string): Promise<{ candles: Candle[], zones: Zone[] }> => {
  const [candlesRes, zonesRes] = await Promise.all([
    fetch(`${API_BASE}/chart?symbol=${symbol}&timeframe=${timeframe}&num_bars=200`),
    fetch(`${API_BASE}/zones?symbol=${symbol}&timeframe=${timeframe}`)
  ]);
  
  if (!candlesRes.ok) throw new Error("Failed to fetch candles");
  if (!zonesRes.ok) throw new Error("Failed to fetch zones");
  
  const candles = await candlesRes.json();
  const zones = await zonesRes.json();
  
  return { candles, zones };
};
