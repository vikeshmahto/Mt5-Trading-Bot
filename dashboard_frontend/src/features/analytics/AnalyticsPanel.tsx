import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTrades } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from "recharts";
import { format } from "date-fns";

export function AnalyticsPanel() {
  const { data: trades = [], isLoading } = useQuery({
    queryKey: ["trades"],
    queryFn: fetchTrades,
  });

  const { metrics, equityCurve, winRateBySetup } = useMemo(() => {
    if (!trades.length) return { metrics: null, equityCurve: [], winRateBySetup: [] };
    
    let totalWins = 0;
    let totalR = 0;
    
    // Reverse to process chronologically for equity curve
    const chronoTrades = [...trades].reverse();
    let cumulativeR = 0;
    const curve = chronoTrades.map(t => {
      if (t.outcome === 'win') totalWins++;
      totalR += t.rMultiple;
      cumulativeR += t.rMultiple;
      return {
        date: format(new Date(t.openedAt), "MMM dd"),
        equity: 10000 + (cumulativeR * 100) // Assuming 1R = $100
      };
    });
    
    const winRate = (totalWins / trades.length) * 100;
    
    const setups = trades.reduce((acc, t) => {
      if (!acc[t.setupType]) acc[t.setupType] = { total: 0, wins: 0 };
      acc[t.setupType].total++;
      if (t.outcome === 'win') acc[t.setupType].wins++;
      return acc;
    }, {} as Record<string, {total: number, wins: number}>);
    
    const setupChartData = Object.entries(setups).map(([name, data]) => ({
      name: name.replace(" confluence", ""),
      winRate: Math.round((data.wins / data.total) * 100)
    }));

    return {
      metrics: {
        winRate: winRate.toFixed(1),
        totalTrades: trades.length,
        avgR: (totalR / trades.length).toFixed(2),
        equity: (10000 + (totalR * 100)).toFixed(2)
      },
      equityCurve: curve,
      winRateBySetup: setupChartData
    };
  }, [trades]);

  if (isLoading || !metrics) {
    return <Card className="h-full"><CardContent className="flex items-center justify-center p-8">Loading analytics...</CardContent></Card>;
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-medium text-muted-foreground">Win Rate</div>
            <div className="text-2xl font-bold">{metrics.winRate}%</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-medium text-muted-foreground">Total Trades</div>
            <div className="text-2xl font-bold">{metrics.totalTrades}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-medium text-muted-foreground">Avg R-Multiple</div>
            <div className="text-2xl font-bold">{metrics.avgR}R</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-medium text-muted-foreground">Total Equity</div>
            <div className="text-2xl font-bold">${metrics.equity}</div>
          </CardContent>
        </Card>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-[300px]">
        <Card className="h-full flex flex-col">
          <CardHeader className="py-3">
            <CardTitle className="text-base">Equity Curve</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 min-h-[250px] pb-2">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={equityCurve} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                <XAxis dataKey="date" stroke="#666" fontSize={12} tickLine={false} />
                <YAxis stroke="#666" fontSize={12} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#111', borderColor: '#333' }}
                  itemStyle={{ color: '#22c55e' }}
                />
                <Line type="monotone" dataKey="equity" stroke="#22c55e" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        
        <Card className="h-full flex flex-col">
          <CardHeader className="py-3">
            <CardTitle className="text-base">Win Rate by Setup</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 min-h-[250px] pb-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={winRateBySetup} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} stroke="#666" fontSize={12} />
                <YAxis dataKey="name" type="category" stroke="#ccc" fontSize={11} width={80} />
                <Tooltip contentStyle={{ backgroundColor: '#111', borderColor: '#333' }} />
                <Bar dataKey="winRate" radius={[0, 4, 4, 0]}>
                  {winRateBySetup.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.winRate > 50 ? '#3b82f6' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
