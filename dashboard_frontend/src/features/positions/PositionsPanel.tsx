import { useSystemStore } from "@/store/useSystemStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { XCircle } from "lucide-react";

export function PositionsPanel() {
  const { positions, closePosition } = useSystemStore();

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="py-4">
        <CardTitle className="text-lg flex justify-between items-center">
          Open Positions
          <span className="text-sm font-normal text-muted-foreground bg-secondary px-2 py-1 rounded-md">
            {positions.length} Active
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-auto p-0">
        {positions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full p-8 text-muted-foreground">
            <XCircle className="h-8 w-8 mb-2 opacity-20" />
            <p>No open positions</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Symbol</TableHead>
                <TableHead>Side</TableHead>
                <TableHead className="text-right">Entry</TableHead>
                <TableHead className="text-right">Current</TableHead>
                <TableHead className="text-right">P&L</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {positions.map((pos) => (
                <TableRow key={pos.id}>
                  <TableCell className="font-medium">{pos.symbol}</TableCell>
                  <TableCell>
                    <span className={`px-2 py-1 rounded-sm text-xs font-bold uppercase ${
                      pos.direction === 'long' ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'
                    }`}>
                      {pos.direction}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono">{pos.entryPrice}</TableCell>
                  <TableCell className="text-right font-mono">{pos.currentPrice}</TableCell>
                  <TableCell className={`text-right font-mono font-semibold ${
                    pos.floatingPnl >= 0 ? 'text-green-500' : 'text-red-500'
                  }`}>
                    {pos.floatingPnl >= 0 ? '+' : ''}{pos.floatingPnl}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      onClick={() => closePosition(pos.id)}
                      className="h-8 px-2 text-muted-foreground hover:text-destructive"
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
