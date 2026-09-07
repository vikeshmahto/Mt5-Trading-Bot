import { useState, useMemo } from "react";
import { useSystemStore } from "@/store/useSystemStore";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { XCircle, ArrowUpDown } from "lucide-react";

export function PositionsPanel() {
  const { positions, closePosition } = useSystemStore();
  
  const [sortField, setSortField] = useState<"symbol" | "direction" | "entryPrice" | "currentPrice" | "floatingPnl">("floatingPnl");
  const [sortDesc, setSortDesc] = useState(true);

  const handleSort = (field: "symbol" | "direction" | "entryPrice" | "currentPrice" | "floatingPnl") => {
    if (sortField === field) {
      setSortDesc(!sortDesc);
    } else {
      setSortField(field);
      setSortDesc(true);
    }
  };

  const sortedPositions = useMemo(() => {
    return [...positions].sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];
      
      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase();
        bVal = String(bVal).toLowerCase();
      }
      
      if (aVal < bVal) return sortDesc ? 1 : -1;
      if (aVal > bVal) return sortDesc ? -1 : 1;
      return 0;
    });
  }, [positions, sortField, sortDesc]);

  const SortIcon = () => <ArrowUpDown className="ml-2 h-4 w-4 inline-block opacity-50 hover:opacity-100" />;

  return (
    <Card className="h-full flex flex-col border-border/40 shadow-sm">
      <CardHeader className="py-4 pb-2 border-b border-border/20">
        <div className="flex justify-between items-center">
          <div>
            <CardTitle className="text-xl font-semibold tracking-tight">Open Positions</CardTitle>
            <CardDescription className="text-muted-foreground mt-1">
              Currently managing {positions.length} active trade{positions.length === 1 ? '' : 's'}
            </CardDescription>
          </div>
          <div className="bg-primary/10 text-primary px-3 py-1 rounded-full text-sm font-medium border border-primary/20 shadow-sm">
            {positions.length} Active
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-auto p-0">
        {positions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full p-12 text-muted-foreground">
            <XCircle className="h-10 w-10 mb-2 opacity-20" />
            <p>No open positions</p>
          </div>
        ) : (
          <Table>
            <TableHeader className="bg-muted/50 sticky top-0 z-10">
              <TableRow>
                <TableHead className="cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort("symbol")}>
                  Symbol {sortField === "symbol" && (sortDesc ? "↓" : "↑")}
                  {sortField !== "symbol" && <SortIcon />}
                </TableHead>
                <TableHead className="cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort("direction")}>
                  Side {sortField === "direction" && (sortDesc ? "↓" : "↑")}
                  {sortField !== "direction" && <SortIcon />}
                </TableHead>
                <TableHead className="text-right cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort("entryPrice")}>
                  Entry {sortField === "entryPrice" && (sortDesc ? "↓" : "↑")}
                  {sortField !== "entryPrice" && <SortIcon />}
                </TableHead>
                <TableHead className="text-right cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort("currentPrice")}>
                  Current {sortField === "currentPrice" && (sortDesc ? "↓" : "↑")}
                  {sortField !== "currentPrice" && <SortIcon />}
                </TableHead>
                <TableHead className="text-right cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort("floatingPnl")}>
                  P&L {sortField === "floatingPnl" && (sortDesc ? "↓" : "↑")}
                  {sortField !== "floatingPnl" && <SortIcon />}
                </TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedPositions.map((pos) => (
                <TableRow key={pos.id} className="hover:bg-muted/30 transition-colors">
                  <TableCell className="font-semibold text-foreground">{pos.symbol}</TableCell>
                  <TableCell>
                    <span className={`px-2 py-0.5 rounded-sm text-xs font-bold uppercase ${
                      pos.direction === 'long' ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'
                    }`}>
                      {pos.direction}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono text-muted-foreground">{pos.entryPrice}</TableCell>
                  <TableCell className="text-right font-mono text-muted-foreground">{pos.currentPrice}</TableCell>
                  <TableCell className={`text-right font-mono font-bold ${
                    pos.floatingPnl >= 0 ? 'text-green-500' : 'text-red-500'
                  }`}>
                    {pos.floatingPnl >= 0 ? '+' : ''}{pos.floatingPnl}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      onClick={() => closePosition(pos.id)}
                      className="h-8 px-3 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                    >
                      Close
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
