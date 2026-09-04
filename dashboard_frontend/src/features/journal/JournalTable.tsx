import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTrades } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";

export function JournalTable() {
  const { data: trades = [], isLoading } = useQuery({
    queryKey: ["trades"],
    queryFn: fetchTrades,
  });

  const [sortField, setSortField] = useState<"openedAt" | "rMultiple" | "outcome">("openedAt");
  const [sortDesc, setSortDesc] = useState(true);

  const handleSort = (field: "openedAt" | "rMultiple" | "outcome") => {
    if (sortField === field) {
      setSortDesc(!sortDesc);
    } else {
      setSortField(field);
      setSortDesc(true);
    }
  };

  const sortedTrades = useMemo(() => {
    return [...trades].sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];
      
      if (sortField === "openedAt") {
        aVal = new Date(a.openedAt).getTime();
        bVal = new Date(b.openedAt).getTime();
      }
      
      if (aVal < bVal) return sortDesc ? 1 : -1;
      if (aVal > bVal) return sortDesc ? -1 : 1;
      return 0;
    });
  }, [trades, sortField, sortDesc]);

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="py-4">
        <CardTitle className="text-lg">Trade Journal</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-auto p-0">
        {isLoading ? (
          <div className="flex items-center justify-center p-8">Loading journal...</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="cursor-pointer" onClick={() => handleSort("openedAt")}>
                  Date {sortField === "openedAt" && (sortDesc ? "↓" : "↑")}
                </TableHead>
                <TableHead>Symbol</TableHead>
                <TableHead>Setup</TableHead>
                <TableHead className="cursor-pointer" onClick={() => handleSort("outcome")}>
                  Outcome {sortField === "outcome" && (sortDesc ? "↓" : "↑")}
                </TableHead>
                <TableHead className="text-right cursor-pointer" onClick={() => handleSort("rMultiple")}>
                  R-Multi {sortField === "rMultiple" && (sortDesc ? "↓" : "↑")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedTrades.map((trade) => (
                <TableRow key={trade.id}>
                  <TableCell className="text-sm">
                    {format(new Date(trade.openedAt), "MMM dd, HH:mm")}
                  </TableCell>
                  <TableCell className="font-medium">{trade.symbol}</TableCell>
                  <TableCell>
                    <span className="text-xs truncate max-w-[120px] inline-block">{trade.setupType}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={`
                      ${trade.outcome === 'win' ? 'text-green-500 border-green-500/50' : ''}
                      ${trade.outcome === 'loss' ? 'text-red-500 border-red-500/50' : ''}
                      ${trade.outcome === 'breakeven' ? 'text-yellow-500 border-yellow-500/50' : ''}
                    `}>
                      {trade.outcome}
                    </Badge>
                  </TableCell>
                  <TableCell className={`text-right font-mono font-bold ${
                    trade.rMultiple > 0 ? 'text-green-500' : trade.rMultiple < 0 ? 'text-red-500' : 'text-yellow-500'
                  }`}>
                    {trade.rMultiple > 0 ? '+' : ''}{trade.rMultiple}R
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
