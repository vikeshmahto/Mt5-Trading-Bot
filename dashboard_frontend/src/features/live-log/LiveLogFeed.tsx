import { useEffect } from "react";
import { useSystemStore } from "@/store/useSystemStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Info, AlertTriangle, XOctagon, CheckCircle2 } from "lucide-react";
import { format } from "date-fns";
import { mockLogs } from "@/lib/mockData";

export function LiveLogFeed() {
  const { logs, addLog, status } = useSystemStore();

  // Simulate incoming logs
  useEffect(() => {
    if (status.botStatus !== "running") return;
    
    const interval = setInterval(() => {
      const isError = Math.random() > 0.95;
      const isWarning = Math.random() > 0.85;
      
      let level: "info" | "warning" | "error" | "success" = "info";
      let message = "Scanning for new SMC setups...";
      
      if (isError) {
        level = "error";
        message = "Failed to fetch tick data from MT5 terminal";
      } else if (isWarning) {
        level = "warning";
        message = "High volatility detected, widening dynamic spread";
      } else if (Math.random() > 0.8) {
        level = "success";
        message = "Identified fresh M15 FVG on XAUUSD";
      }
      
      addLog({
        timestamp: new Date().toISOString(),
        level,
        message
      });
    }, 4000); // Every 4 seconds
    
    return () => clearInterval(interval);
  }, [addLog, status.botStatus]);

  const getIcon = (level: string) => {
    switch (level) {
      case "info": return <Info className="h-4 w-4 text-blue-500" />;
      case "warning": return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case "error": return <XOctagon className="h-4 w-4 text-red-500" />;
      case "success": return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      default: return <Info className="h-4 w-4" />;
    }
  };

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="py-4 border-b">
        <CardTitle className="text-lg flex items-center gap-2">
          <div className={`h-2 w-2 rounded-full ${status.botStatus === 'running' ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`} />
          System Logs
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-auto p-0 bg-black/40">
        <div className="flex flex-col p-4 gap-2 font-mono text-sm">
          {logs.map((log) => (
            <div key={log.id} className="flex items-start gap-3 border-b border-white/5 pb-2 last:border-0">
              <span className="text-muted-foreground whitespace-nowrap text-xs mt-0.5">
                {format(new Date(log.timestamp), "HH:mm:ss")}
              </span>
              <div className="mt-0.5 shrink-0">
                {getIcon(log.level)}
              </div>
              <span className={`flex-1 break-words leading-tight ${
                log.level === 'error' ? 'text-red-400' :
                log.level === 'warning' ? 'text-yellow-400' :
                log.level === 'success' ? 'text-green-400' : 'text-gray-300'
              }`}>
                {log.message}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
