import { useEffect, useState, useRef, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchLogs } from "@/lib/api";
import { LogEntry } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Info, AlertTriangle, XOctagon, CheckCircle2, Search, Trash2 } from "lucide-react";
import { format } from "date-fns";

export function LiveLogFeed() {
  const [liveLogs, setLiveLogs] = useState<LogEntry[]>([]);
  const [filterLevel, setFilterLevel] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Initial load from DB
  const { data: initialLogs } = useQuery({
    queryKey: ["logs"],
    queryFn: () => fetchLogs(100),
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (initialLogs && liveLogs.length === 0) {
      setLiveLogs(initialLogs);
    }
  }, [initialLogs]);

  // Connect WebSocket for live streaming updates
  useEffect(() => {
    let reconnectTimeout: any;

    const connectWs = () => {
      const wsUrl = "ws://localhost:8000/ws/live";
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "log" && payload.data) {
            setLiveLogs((prev) => [payload.data, ...prev.slice(0, 199)]);
          }
        } catch {
          // Ignore non-json or unhandled messages
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        reconnectTimeout = setTimeout(connectWs, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connectWs();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const filteredLogs = useMemo(() => {
    return liveLogs.filter((log) => {
      if (filterLevel !== "all" && log.level !== filterLevel) return false;
      if (
        searchQuery &&
        !log.message.toLowerCase().includes(searchQuery.toLowerCase())
      )
        return false;
      return true;
    });
  }, [liveLogs, filterLevel, searchQuery]);

  const getIcon = (level: string) => {
    switch (level) {
      case "info":
        return <Info className="h-4 w-4 text-blue-400" />;
      case "warning":
        return <AlertTriangle className="h-4 w-4 text-amber-400" />;
      case "error":
        return <XOctagon className="h-4 w-4 text-red-400" />;
      case "success":
        return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
      default:
        return <Info className="h-4 w-4" />;
    }
  };

  const levelCounts = useMemo(() => {
    return {
      all: liveLogs.length,
      info: liveLogs.filter((l) => l.level === "info").length,
      success: liveLogs.filter((l) => l.level === "success").length,
      warning: liveLogs.filter((l) => l.level === "warning").length,
      error: liveLogs.filter((l) => l.level === "error").length,
    };
  }, [liveLogs]);

  return (
    <Card className="h-full flex flex-col border-border/40 bg-card/70 backdrop-blur-sm shadow-sm">
      <CardHeader className="py-3.5 px-4 border-b border-border/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div
            className={`h-2.5 w-2.5 rounded-full ${
              wsConnected
                ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse"
                : "bg-amber-500"
            }`}
          />
          <CardTitle className="text-base font-bold text-foreground">
            System Console Telemetry
          </CardTitle>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 border border-border/40 text-muted-foreground">
            {wsConnected ? "STREAM LIVE" : "CONNECTING..."}
          </span>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Search box */}
          <div className="relative flex items-center">
            <Search className="h-3.5 w-3.5 absolute left-2.5 text-muted-foreground pointer-events-none" />
            <input
              type="text"
              placeholder="Search logs…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-7 w-36 lg:w-48 pl-8 pr-2 text-xs bg-background/80 border border-border/40 rounded-md focus:outline-none focus:border-emerald-500/50"
            />
          </div>

          {/* Level Pills */}
          <div className="flex items-center gap-1 bg-background/80 p-0.5 rounded-md border border-border/40">
            {(["all", "info", "success", "warning", "error"] as const).map(
              (lvl) => (
                <button
                  key={lvl}
                  onClick={() => setFilterLevel(lvl)}
                  className={`px-2 py-0.5 text-[10px] font-bold rounded uppercase transition-colors ${
                    filterLevel === lvl
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {lvl} ({levelCounts[lvl]})
                </button>
              )
            )}
          </div>

          {/* Clear button */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setLiveLogs([])}
            className="h-7 w-7 text-muted-foreground hover:text-red-400"
            title="Clear display logs"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex-1 overflow-auto p-0 bg-black/50">
        <div className="flex flex-col p-4 gap-1.5 font-mono text-xs">
          {filteredLogs.length === 0 ? (
            <div className="text-muted-foreground text-xs py-16 text-center">
              No matching log records found in buffer.
            </div>
          ) : (
            filteredLogs.map((log) => (
              <div
                key={log.id}
                className="flex items-start gap-2.5 py-1 px-1.5 rounded hover:bg-white/[0.03] transition-colors"
              >
                <span className="text-muted-foreground/60 whitespace-nowrap text-[11px] select-none shrink-0 font-mono">
                  {format(new Date(log.timestamp), "HH:mm:ss.SSS")}
                </span>
                <div className="mt-0.5 shrink-0">{getIcon(log.level)}</div>
                <span
                  className={`flex-1 break-all leading-snug ${
                    log.level === "error"
                      ? "text-red-400 font-semibold"
                      : log.level === "warning"
                      ? "text-amber-400"
                      : log.level === "success"
                      ? "text-emerald-400 font-medium"
                      : "text-neutral-300"
                  }`}
                >
                  {log.message}
                </span>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}


