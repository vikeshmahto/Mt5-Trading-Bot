import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTrades } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";
import { ArrowUpDown, Search, ChevronLeft, ChevronRight, FilterX } from "lucide-react";

export function JournalTable() {
  const { data: trades = [], isLoading } = useQuery({
    queryKey: ["trades"],
    queryFn: fetchTrades,
  });

  // State
  const [sortField, setSortField] = useState<"openedAt" | "symbol" | "setupType" | "rMultiple" | "outcome">("openedAt");
  const [sortDesc, setSortDesc] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  
  // Filters
  const [searchSymbol, setSearchSymbol] = useState("");
  const [filterOutcome, setFilterOutcome] = useState<string>("all");
  const [filterSetup, setFilterSetup] = useState<string>("all");

  const handleSort = (field: "openedAt" | "symbol" | "setupType" | "rMultiple" | "outcome") => {
    if (sortField === field) {
      setSortDesc(!sortDesc);
    } else {
      setSortField(field);
      setSortDesc(true);
    }
  };

  const clearFilters = () => {
    setSearchSymbol("");
    setFilterOutcome("all");
    setFilterSetup("all");
    setPage(1);
  };

  // Extract unique setup types for the filter dropdown
  const uniqueSetups = useMemo(() => {
    return Array.from(new Set(trades.map(t => t.setupType))).filter(Boolean);
  }, [trades]);

  const filteredTrades = useMemo(() => {
    return trades.filter((trade) => {
      if (searchSymbol && !trade.symbol.toLowerCase().includes(searchSymbol.toLowerCase())) return false;
      if (filterOutcome !== "all" && trade.outcome !== filterOutcome) return false;
      if (filterSetup !== "all" && trade.setupType !== filterSetup) return false;
      return true;
    });
  }, [trades, searchSymbol, filterOutcome, filterSetup]);

  const sortedTrades = useMemo(() => {
    return [...filteredTrades].sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];
      
      if (sortField === "openedAt") {
        aVal = new Date(a.openedAt).getTime();
        bVal = new Date(b.openedAt).getTime();
      } else if (sortField === "rMultiple") {
        aVal = Number(a.rMultiple) || 0;
        bVal = Number(b.rMultiple) || 0;
      } else {
        // String comparison
        aVal = String(aVal).toLowerCase();
        bVal = String(bVal).toLowerCase();
      }
      
      if (aVal < bVal) return sortDesc ? 1 : -1;
      if (aVal > bVal) return sortDesc ? -1 : 1;
      return 0;
    });
  }, [filteredTrades, sortField, sortDesc]);

  // Pagination
  const totalPages = Math.ceil(sortedTrades.length / pageSize) || 1;
  const paginatedTrades = sortedTrades.slice((page - 1) * pageSize, page * pageSize);

  // Reset to page 1 if filters change and current page is out of bounds
  if (page > totalPages) setPage(totalPages);

  const SortIcon = () => <ArrowUpDown className="ml-2 h-4 w-4 inline-block opacity-50 hover:opacity-100" />;

  return (
    <Card className="h-full flex flex-col border-border/40 shadow-sm">
      <CardHeader className="py-4 pb-2 border-b border-border/20">
        <div className="flex justify-between items-center">
          <div>
            <CardTitle className="text-xl font-semibold tracking-tight">Trade Journal</CardTitle>
            <CardDescription className="text-muted-foreground mt-1">
              {filteredTrades.length} records found
            </CardDescription>
          </div>
        </div>
        
        {/* Filters Bar */}
        <div className="flex flex-wrap items-center gap-3 mt-4">
          <div className="relative w-full max-w-xs">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input 
              type="text" 
              placeholder="Filter by symbol..." 
              className="w-full h-9 pl-9 pr-3 rounded-md border border-input bg-transparent text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={searchSymbol}
              onChange={(e) => setSearchSymbol(e.target.value)}
            />
          </div>
          
          <select 
            className="h-9 px-3 rounded-md border border-input bg-transparent text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={filterOutcome}
            onChange={(e) => setFilterOutcome(e.target.value)}
          >
            <option value="all">All Outcomes</option>
            <option value="win">Wins Only</option>
            <option value="loss">Losses Only</option>
            <option value="breakeven">Breakeven</option>
          </select>

          <select 
            className="h-9 px-3 rounded-md border border-input bg-transparent text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring max-w-[200px]"
            value={filterSetup}
            onChange={(e) => setFilterSetup(e.target.value)}
          >
            <option value="all">All Setups</option>
            {uniqueSetups.map(setup => (
              <option key={setup} value={setup}>{setup}</option>
            ))}
          </select>

          {(searchSymbol || filterOutcome !== "all" || filterSetup !== "all") && (
            <button 
              onClick={clearFilters}
              className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none hover:bg-accent hover:text-accent-foreground h-9 px-3 border border-dashed border-border"
            >
              <FilterX className="mr-2 h-4 w-4" />
              Reset
            </button>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="flex-1 overflow-auto p-0">
        {isLoading ? (
          <div className="flex items-center justify-center p-12 text-muted-foreground">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mr-3"></div>
            Loading journal entries...
          </div>
        ) : paginatedTrades.length === 0 ? (
           <div className="flex flex-col items-center justify-center p-12 text-muted-foreground">
             <FilterX className="h-10 w-10 mb-2 opacity-20" />
             <p>No trades match your filters</p>
           </div>
        ) : (
          <Table>
            <TableHeader className="bg-muted/50 sticky top-0 z-10">
              <TableRow>
                <TableHead className="cursor-pointer select-none whitespace-nowrap hover:text-foreground transition-colors" onClick={() => handleSort("openedAt")}>
                  Date & Time {sortField === "openedAt" && (sortDesc ? "↓" : "↑")}
                  {sortField !== "openedAt" && <SortIcon />}
                </TableHead>
                <TableHead className="cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort("symbol")}>
                  Symbol {sortField === "symbol" && (sortDesc ? "↓" : "↑")}
                  {sortField !== "symbol" && <SortIcon />}
                </TableHead>
                <TableHead className="cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort("setupType")}>
                  Setup {sortField === "setupType" && (sortDesc ? "↓" : "↑")}
                  {sortField !== "setupType" && <SortIcon />}
                </TableHead>
                <TableHead className="cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort("outcome")}>
                  Outcome {sortField === "outcome" && (sortDesc ? "↓" : "↑")}
                  {sortField !== "outcome" && <SortIcon />}
                </TableHead>
                <TableHead className="text-right cursor-pointer select-none hover:text-foreground transition-colors" onClick={() => handleSort("rMultiple")}>
                  R-Multi {sortField === "rMultiple" && (sortDesc ? "↓" : "↑")}
                  {sortField !== "rMultiple" && <SortIcon />}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedTrades.map((trade) => (
                <TableRow key={trade.id} className="hover:bg-muted/30 transition-colors">
                  <TableCell className="text-sm font-medium">
                    {format(new Date(trade.openedAt), "MMM dd, yyyy HH:mm")}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-foreground">{trade.symbol}</span>
                      <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded-sm ${trade.direction === 'long' ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}`}>
                        {trade.direction}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className="text-xs truncate max-w-[150px] inline-block text-muted-foreground font-medium">{trade.setupType}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={`
                      capitalize font-medium shadow-sm
                      ${trade.outcome === 'win' ? 'text-green-500 border-green-500/30 bg-green-500/5' : ''}
                      ${trade.outcome === 'loss' ? 'text-red-500 border-red-500/30 bg-red-500/5' : ''}
                      ${trade.outcome === 'breakeven' ? 'text-yellow-500 border-yellow-500/30 bg-yellow-500/5' : ''}
                      ${!trade.outcome ? 'text-blue-500 border-blue-500/30 bg-blue-500/5' : ''}
                    `}>
                      {trade.outcome || 'Active'}
                    </Badge>
                  </TableCell>
                  <TableCell className={`text-right font-mono font-bold ${
                    trade.rMultiple > 0 ? 'text-green-500' : trade.rMultiple < 0 ? 'text-red-500' : 'text-yellow-500'
                  }`}>
                    {trade.rMultiple !== null && trade.rMultiple !== undefined ? `${trade.rMultiple > 0 ? '+' : ''}${trade.rMultiple}R` : '-'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      
      {/* Pagination Footer */}
      {!isLoading && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-border/20 bg-muted/10">
          <div className="flex items-center text-sm text-muted-foreground">
            <span className="mr-2">Rows per page</span>
            <select 
              className="h-7 w-16 rounded-md border border-input bg-transparent px-2 text-xs focus-visible:outline-none"
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
            >
              <option value="5">5</option>
              <option value="10">10</option>
              <option value="20">20</option>
              <option value="50">50</option>
            </select>
          </div>
          
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-input bg-transparent hover:bg-accent hover:text-accent-foreground disabled:opacity-50 disabled:pointer-events-none transition-colors"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages || totalPages === 0}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-input bg-transparent hover:bg-accent hover:text-accent-foreground disabled:opacity-50 disabled:pointer-events-none transition-colors"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
