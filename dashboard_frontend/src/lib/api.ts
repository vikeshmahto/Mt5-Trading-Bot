import { Trade, Position, SystemStatus, Candle, Zone } from "./types";
import { mockTrades, mockPositions, mockSystemStatus, generateCandles, mockZones } from "./mockData";

// Simulate network latency
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export const fetchSystemStatus = async (): Promise<SystemStatus> => {
  await delay(400);
  return mockSystemStatus;
};

export const fetchPositions = async (): Promise<Position[]> => {
  await delay(500);
  return mockPositions; // Note: In the real app, this might just initialize the store, and WS handles updates
};

export const fetchTrades = async (): Promise<Trade[]> => {
  await delay(600);
  return mockTrades;
};

export const fetchChartData = async (symbol: string, timeframe: string): Promise<{ candles: Candle[], zones: Zone[] }> => {
  await delay(800);
  // In mock, we ignore symbol/timeframe and just return new generated data so the chart updates
  const candles = generateCandles(200, 2000);
  
  // Create some zones relative to the newly generated candles
  const zones: Zone[] = [
    {
      type: "orderblock",
      startTime: candles[candles.length - 50].time,
      endTime: candles[candles.length - 30].time,
      priceHigh: candles[candles.length - 40].high,
      priceLow: candles[candles.length - 40].low,
      timeframe
    },
    {
      type: "fvg",
      startTime: candles[candles.length - 20].time,
      endTime: candles[candles.length - 5].time,
      priceHigh: candles[candles.length - 15].high,
      priceLow: candles[candles.length - 15].low,
      timeframe
    }
  ];
  
  return { candles, zones };
};
