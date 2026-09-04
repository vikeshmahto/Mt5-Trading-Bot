import { useSystemStore } from "@/store/useSystemStore";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, Pause, Activity, Globe } from "lucide-react";

export function StatusBar() {
  const { status, toggleBot } = useSystemStore();

  const getDotColor = () => {
    switch (status.botStatus) {
      case "running":
        return "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)] animate-pulse";
      case "paused":
        return "bg-yellow-500";
      case "stopped":
        return "bg-red-500";
    }
  };

  return (
    <div className="flex flex-wrap items-center justify-between p-3 border-b bg-card text-card-foreground gap-4">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className={`h-3 w-3 rounded-full ${getDotColor()}`} />
          <span className="font-semibold capitalize">
            {status.botStatus}
          </span>
        </div>
        
        <div className="h-6 w-px bg-border" />
        
        <Badge variant="outline" className="gap-1">
          <Activity className="h-3 w-3" />
          XAUUSD / M15
        </Badge>
        
        <Badge variant={status.regime === "trending" ? "default" : "secondary"}>
          Regime: {status.regime}
        </Badge>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Globe className={`h-4 w-4 ${status.mt5Connected ? 'text-green-500' : 'text-red-500'}`} />
          MT5 {status.mt5Connected ? 'Connected' : 'Disconnected'}
        </div>
        
        <Button 
          variant={status.botStatus === "running" ? "outline" : "default"} 
          size="sm" 
          onClick={toggleBot}
          className="gap-2"
        >
          {status.botStatus === "running" ? (
            <>
              <Pause className="h-4 w-4" /> Pause
            </>
          ) : (
            <>
              <Play className="h-4 w-4" /> Resume
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
