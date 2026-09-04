import { useEffect, useRef, useState } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  Time,
  CandlestickSeries,
  createSeriesMarkers,
} from "lightweight-charts";
import { useQuery } from "@tanstack/react-query";
import { fetchChartData } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const TIMEFRAMES = ["M1", "M15", "H1", "H4", "D1"];

export function ChartPanel() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [timeframe, setTimeframe] = useState("M15");

  const { data, isLoading } = useQuery({
    queryKey: ["chartData", "XAUUSD", timeframe],
    queryFn: () => fetchChartData("XAUUSD", timeframe),
    refetchInterval: false,
  });

  // Initialize chart once on mount
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#d1d5db",
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: "#374151",
      },
      rightPriceScale: {
        borderColor: "#374151",
      },
      crosshair: {
        vertLine: { color: "#6b7280" },
        horzLine: { color: "#6b7280" },
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight || 420,
    });

    chartRef.current = chart;

    // lightweight-charts v5 API: addSeries(CandlestickSeries, options)
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    seriesRef.current = series;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight || 420,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Update data when query resolves
  useEffect(() => {
    if (!seriesRef.current || !data) return;

    seriesRef.current.setData(
      data.candles.map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    // lightweight-charts v5: use createSeriesMarkers for zone markers
    const markers = data.zones.map((z) => ({
      time: z.startTime as Time,
      position:
        z.type === "orderblock" ? ("aboveBar" as const) : ("belowBar" as const),
      color: z.type === "orderblock" ? "#ef4444" : "#06b6d4",
      shape: "circle" as const,
      text: z.type === "orderblock" ? "OB" : "FVG",
    }));

    createSeriesMarkers(
      seriesRef.current,
      markers.sort((a, b) => (a.time as number) - (b.time as number))
    );

    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <Card className="h-full flex flex-col col-span-1 lg:col-span-2 xl:col-span-3">
      <CardHeader className="py-3 flex flex-row items-center justify-between border-b">
        <CardTitle className="text-lg font-semibold">
          XAUUSD — {timeframe}
        </CardTitle>
        <div className="flex gap-1">
          {TIMEFRAMES.map((tf) => (
            <Button
              key={tf}
              variant={timeframe === tf ? "default" : "ghost"}
              size="sm"
              onClick={() => setTimeframe(tf)}
              className="h-7 text-xs px-2"
            >
              {tf}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="flex-1 p-0 relative min-h-[420px]">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/70 z-10 rounded-b-lg">
            <span className="animate-pulse text-muted-foreground font-medium">
              Loading Chart…
            </span>
          </div>
        )}
        <div ref={chartContainerRef} className="w-full h-full min-h-[420px]" />
      </CardContent>
    </Card>
  );
}
