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

export const createTrade = async (data: Partial<Trade>): Promise<Trade> => {
  const res = await fetch(`${API_BASE}/trades`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create trade");
  return res.json();
};

export const updateTrade = async (id: string, data: Partial<Trade>): Promise<Trade> => {
  const res = await fetch(`${API_BASE}/trades/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update trade");
  return res.json();
};

export const deleteTrade = async (id: string): Promise<{ status: string }> => {
  const res = await fetch(`${API_BASE}/trades/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete trade");
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

export const closePosition = async (positionId: string): Promise<{ status: string; dryRun: boolean }> => {
  const res = await fetch(`${API_BASE}/positions/${positionId}/close`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to close position");
  return res.json();
};

export const pauseBot = async (): Promise<{ botStatus: string }> => {
  const res = await fetch(`${API_BASE}/status/pause`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to pause bot");
  return res.json();
};

export const resumeBot = async (): Promise<{ botStatus: string }> => {
  const res = await fetch(`${API_BASE}/status/resume`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to resume bot");
  return res.json();
};

export const forceSignal = async (): Promise<{ status: string }> => {
  const res = await fetch(`${API_BASE}/status/force-signal`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to force signal");
  return res.json();
};

export interface RiskConfig {
  riskPerTrade: number;
  dailyCircuitBreaker: boolean;
  maxDailyLoss: number;
  activeSetups: Record<string, boolean>;
}

export const fetchConfig = async (): Promise<RiskConfig> => {
  const res = await fetch(`${API_BASE}/config`);
  if (!res.ok) throw new Error("Failed to fetch config");
  return res.json();
};

export const updateConfig = async (payload: Partial<RiskConfig>): Promise<{ status: string }> => {
  const res = await fetch(`${API_BASE}/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error("Failed to update config");
  return res.json();
};

export const fetchLogs = async (limit: number = 50) => {
  const res = await fetch(`${API_BASE}/logs?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch logs");
  return res.json();
};
