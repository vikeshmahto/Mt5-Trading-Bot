import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchConfig, updateConfig } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardFooter, CardDescription } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

export function RiskConfigPanel() {
  const queryClient = useQueryClient();

  const [riskPerTrade, setRiskPerTrade] = useState(1.0);
  const [maxDailyLoss, setMaxDailyLoss] = useState(3.0);
  const [enableCircuitBreaker, setEnableCircuitBreaker] = useState(false);
  
  const [setups, setSetups] = useState<Record<string, boolean>>({
    "OB+FVG confluence": true,
    "Liquidity Sweep": true,
    "BOS Breakout": false,
    "Trendline Bounce": false,
  });

  const { data: config, isLoading } = useQuery({
    queryKey: ["riskConfig"],
    queryFn: fetchConfig,
  });

  useEffect(() => {
    if (config) {
      setRiskPerTrade(config.riskPerTrade ?? 1.0);
      setMaxDailyLoss(config.maxDailyLoss ?? 3.0);
      setEnableCircuitBreaker(config.dailyCircuitBreaker ?? false);
      if (config.activeSetups) {
        setSetups(config.activeSetups);
      }
    }
  }, [config]);

  const saveMutation = useMutation({
    mutationFn: () => updateConfig({
      riskPerTrade,
      dailyCircuitBreaker: enableCircuitBreaker,
      maxDailyLoss,
      activeSetups: setups,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["riskConfig"] });
      toast.success("Risk configuration saved successfully", {
        description: "Changes have been updated in the database."
      });
    },
    onError: (err: any) => {
      toast.error(`Failed to save configuration: ${err.message}`);
    }
  });

  const toggleSetup = (key: string) => {
    setSetups(prev => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="py-4 border-b">
        <CardTitle className="text-lg flex items-center justify-between">
          Risk & Strategy Config
          {isLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
        </CardTitle>
        <CardDescription>Adjust position sizing and setup filters</CardDescription>
      </CardHeader>
      
      <CardContent className="flex-1 overflow-auto p-4 space-y-6">
        <div className="space-y-4">
          <h4 className="font-semibold text-sm">Global Risk Parameters</h4>
          
          <div className="grid gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Risk Per Trade (%)</label>
              <input 
                type="number" 
                step="0.1" 
                value={riskPerTrade} 
                onChange={e => setRiskPerTrade(parseFloat(e.target.value) || 0)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>
            
            <div className="flex items-center justify-between border rounded-md p-3">
              <div className="space-y-0.5">
                <label className="text-sm font-medium">Daily Circuit Breaker</label>
                <div className="text-xs text-muted-foreground">Pause bot if loss exceeds limit</div>
              </div>
              <Switch 
                checked={enableCircuitBreaker} 
                onCheckedChange={setEnableCircuitBreaker} 
              />
            </div>
            
            {enableCircuitBreaker && (
              <div className="flex flex-col gap-1.5 pl-2 border-l-2 border-primary/20">
                <label className="text-sm font-medium">Max Daily Loss (%)</label>
                <input 
                  type="number" 
                  step="0.5" 
                  value={maxDailyLoss} 
                  onChange={e => setMaxDailyLoss(parseFloat(e.target.value) || 0)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                />
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <h4 className="font-semibold text-sm">Active Setups</h4>
          <div className="space-y-2">
            {Object.entries(setups).map(([setup, isActive]) => (
              <div key={setup} className="flex items-center justify-between border rounded-md p-2 px-3">
                <span className="text-sm">{setup}</span>
                <Switch 
                  checked={isActive} 
                  onCheckedChange={() => toggleSetup(setup)} 
                />
              </div>
            ))}
          </div>
        </div>
      </CardContent>
      
      <CardFooter className="py-3 border-t">
        <Button 
          className="w-full" 
          disabled={saveMutation.isPending}
          onClick={() => saveMutation.mutate()}
        >
          {saveMutation.isPending ? "Saving…" : "Save Configuration"}
        </Button>
      </CardFooter>
    </Card>
  );
}

