import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchTrades, deleteTrade } from "@/lib/api";
import { Trade } from "@/lib/types";
import { TradeDetailModal } from "./TradeDetailModal";
import { AddTradeModal } from "./AddTradeModal";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { format } from "date-fns";
import {
  ArrowUpDown,
  Search,
  ChevronLeft,
  ChevronRight,
  FilterX,
  PlusCircle,
  Award,
  Target,
  Brain,
  AlertOctagon,
  Download,
  Trash2,
  SlidersHorizontal,
} from "lucide-react";
import { toast } from "sonner";

export function JournalTable() {
  const queryClient = useQueryClient();

  const { data: trades = [], isLoading } = useQuery({
    queryKey: ["trades"],
    queryFn: fetchTrades,
  });

  const [selectedTrade, setSelectedTrade] = useState<Trade | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isAddOpen, setIsAddOpen] = useState(false);

  // Sorting & Pagination
  const [sortField, setSortField] = useState<
    "openedAt" | "symbol" | "setupType" | "rMultiple" | "outcome" | "pointsCaptured"
  >("openedAt");
  const [sortDesc, setSortDesc] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [filterSource, setFilterSource] = useState<string>("all");
  const [filterOutcome, setFilterOutcome] = useState<string>("all");
  const [filterSetup, setFilterSetup] = useState<string>("all");
  const [filterSession, setFilterSession] = useState<string>("all");
  const [filterMistake, setFilterMistake] = useState<string>("all");

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTrade(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trades"] });
      toast.success("Trade removed from journal");
    },
    onError: (err: any) => {
      toast.error(`Failed to delete trade: ${err.message}`);
    },
  });

  // Diagnostics calculations across all trades
  const diagnostics = useMemo(() => {
    if (!trades.length) {
      return {
        totalPoints: 0,
        winRate: "0.0",
        topSetup: "N/A",
        topMistake: "None",
        adherenceRate: "100.0",
      };
    }

    let points = 0;
    let wins = 0;
    let adhered = 0;
    const setupCounts: Record<string, { total: number; wins: number }> = {};
    const mistakeCounts: Record<string, number> = {};

    for (const t of trades) {
      points += t.pointsCaptured || 0;
      if (t.outcome === "win") wins++;
      if (!t.ruleAdherence || t.ruleAdherence === "followed_rules") adhered++;

      // Setups
      if (!setupCounts[t.setupType]) setupCounts[t.setupType] = { total: 0, wins: 0 };
      setupCounts[t.setupType].total++;
      if (t.outcome === "win") setupCounts[t.setupType].wins++;

      // Mistakes on losses
      if (t.outcome === "loss" && t.mistakeType && t.mistakeType !== "clean") {
        mistakeCounts[t.mistakeType] = (mistakeCounts[t.mistakeType] || 0) + 1;
      }
    }

    // Top setup by win rate (min 1 trade)
    let bestSetup = "N/A";
    let bestRate = -1;
    for (const [st, counts] of Object.entries(setupCounts)) {
      const rate = counts.wins / counts.total;
      if (rate > bestRate) {
        bestRate = rate;
        bestSetup = `${st.replace(" confluence", "")} (${Math.round(rate * 100)}%)`;
      }
    }

    // Top mistake
    let maxMistake = "None (Clean Execution)";
    let maxCount = 0;
    for (const [m, count] of Object.entries(mistakeCounts)) {
      if (count > maxCount) {
        maxCount = count;
        maxMistake = `${m.replace(/_/g, " ")} (${count} losses)`;
      }
    }

    return {
      totalPoints: Number(points.toFixed(1)),
      winRate: ((wins / trades.length) * 100).toFixed(1),
      topSetup: bestSetup,
      topMistake: maxMistake,
      adherenceRate: ((adhered / trades.length) * 100).toFixed(1),
    };
  }, [trades]);

  const uniqueSetups = useMemo(() => {
    return Array.from(new Set(trades.map((t) => t.setupType))).filter(Boolean);
  }, [trades]);

  const uniqueMistakes = useMemo(() => {
    return Array.from(new Set(trades.map((t) => t.mistakeType))).filter(Boolean);
  }, [trades]);

  const filteredTrades = useMemo(() => {
    return trades.filter((trade) => {
      if (
        searchQuery &&
        !trade.symbol.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !(trade.reviewNotes || "").toLowerCase().includes(searchQuery.toLowerCase()) &&
        !(trade.mistakeType || "").toLowerCase().includes(searchQuery.toLowerCase())
      ) {
        return false;
      }
      if (filterSource !== "all" && (trade.source || "paper") !== filterSource) return false;
      if (filterOutcome !== "all" && trade.outcome !== filterOutcome) return false;
      if (filterSetup !== "all" && trade.setupType !== filterSetup) return false;
      if (filterSession !== "all" && trade.session !== filterSession) return false;
      if (filterMistake !== "all" && trade.mistakeType !== filterMistake) return false;
      return true;
    });
  }, [trades, searchQuery, filterSource, filterOutcome, filterSetup, filterSession, filterMistake]);

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
      } else if (sortField === "pointsCaptured") {
        aVal = Number(a.pointsCaptured) || 0;
        bVal = Number(b.pointsCaptured) || 0;
      } else {
        aVal = String(aVal || "").toLowerCase();
        bVal = String(bVal || "").toLowerCase();
      }

      if (aVal < bVal) return sortDesc ? 1 : -1;
      if (aVal > bVal) return sortDesc ? -1 : 1;
      return 0;
    });
  }, [filteredTrades, sortField, sortDesc]);

  const totalPages = Math.ceil(sortedTrades.length / pageSize) || 1;
  const paginatedTrades = useMemo(() => {
    const start = (page - 1) * pageSize;
    return sortedTrades.slice(start, start + pageSize);
  }, [sortedTrades, page, pageSize]);

  const handleSort = (
    field: "openedAt" | "symbol" | "setupType" | "rMultiple" | "outcome" | "pointsCaptured"
  ) => {
    if (sortField === field) {
      setSortDesc(!sortDesc);
    } else {
      setSortField(field);
      setSortDesc(true);
    }
  };

  const clearFilters = () => {
    setSearchQuery("");
    setFilterSource("all");
    setFilterOutcome("all");
    setFilterSetup("all");
    setFilterSession("all");
    setFilterMistake("all");
    setPage(1);
  };

  const exportCSV = () => {
    const exportData = filteredTrades.length ? filteredTrades : trades;
    if (!exportData.length) {
      toast.info("No trades to export");
      return;
    }

    const esc = (v: string | number | null | undefined): string => {
      if (v === null || v === undefined || v === "") return "";
      const s = String(v);
      // Wrap in quotes if contains comma, quote, or newline
      if (s.includes(",") || s.includes('"') || s.includes("\n")) {
        return `"${s.replace(/"/g, '""')}"`;
      }
      return s;
    };

    const headers = [
      "Trade ID",
      "Trade Source",
      "Symbol",
      "Date/Time (Open)",
      "Date/Time (Close)",
      "Session",
      "HTF Bias (D1/H4/H1)",
      "HTF Reason / Key Levels",
      "Bias Correct in Hindsight?",
      "Setup Pattern",
      "Setup Timeframe",
      "Confluence Level",
      "Screenshot URL",
      "Direction",
      "Entry Price",
      "Stop Loss",
      "Take Profit",
      "Exit Price",
      "Entry Timeframe",
      "Entry Trigger",
      "SL Logic",
      "Planned R:R",
      "Risk % Account",
      "Outcome",
      "R Multiple",
      "Points Captured",
      "MAE (Max Adverse Excursion)",
      "MFE (Max Favorable Excursion)",
      "Rule Adherence",
      "Emotional State",
      "External Factor",
      "Textbook Comparison",
      "Mistake Type",
      "Review Notes",
    ];

    const rows = exportData.map((t) => [
      esc(t.id),
      esc(t.source || "paper"),
      esc(t.symbol),
      esc(t.openedAt ? format(new Date(t.openedAt), "yyyy-MM-dd HH:mm") : ""),
      esc(t.closedAt ? format(new Date(t.closedAt), "yyyy-MM-dd HH:mm") : ""),
      esc(t.session),
      esc(t.htfBias),
      esc(t.htfReason),
      esc(t.biasCorrect),
      esc(t.setupType),
      esc(t.setupTimeframe),
      esc(t.confluence),
      esc(t.screenshotUrl),
      esc(t.direction),
      esc(t.entryPrice),
      esc(t.sl),
      esc(t.tp),
      esc(t.exitPrice),
      esc(t.entryTimeframe),
      esc(t.entryTrigger),
      esc(t.slLogic),
      esc(t.plannedRr),
      esc(t.riskPct),
      esc(t.outcome),
      esc(t.rMultiple),
      esc(t.pointsCaptured),
      esc(t.mae),
      esc(t.mfe),
      esc(t.ruleAdherence),
      esc(t.emotionalState),
      esc(t.externalFactor),
      esc(t.textbookComparison),
      esc(t.mistakeType),
      esc(t.reviewNotes),
    ]);

    // BOM + CSV so Excel opens with correct encoding
    const BOM = "\uFEFF";
    const csvContent =
      BOM +
      [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute(
      "download",
      `SMC_Trade_Journal_${format(new Date(), "yyyy-MM-dd")}.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success(`Exported ${trades.length} trades — all 6 diagnostic pillars included`);
  };


  const SortIcon = () => (
    <ArrowUpDown className="ml-1 h-3.5 w-3.5 inline-block opacity-40 hover:opacity-100" />
  );

  return (
    <div className="flex flex-col gap-5">
      {/* Top SMC Diagnostics Ribbon */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Points Captured */}
        <Card className="bg-card/70 border-border/40 backdrop-blur-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground uppercase font-semibold">
                Gold Points Captured
              </span>
              <Award className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-black font-mono text-emerald-400 mt-1">
              {diagnostics.totalPoints >= 0 ? "+" : ""}
              {diagnostics.totalPoints} pts
            </div>
            <span className="text-[11px] text-muted-foreground">
              Target: ~10.0 pts / trade standard
            </span>
          </CardContent>
        </Card>

        {/* Highest Edge Setup */}
        <Card className="bg-card/70 border-border/40 backdrop-blur-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground uppercase font-semibold">
                Top Setup Edge
              </span>
              <Target className="h-4 w-4 text-cyan-400" />
            </div>
            <div className="text-sm font-bold text-foreground truncate mt-1">
              {diagnostics.topSetup}
            </div>
            <span className="text-[11px] text-muted-foreground">
              Win rate: {diagnostics.winRate}% across {trades.length} trades
            </span>
          </CardContent>
        </Card>

        {/* Primary Loss Cause */}
        <Card className="bg-card/70 border-border/40 backdrop-blur-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground uppercase font-semibold">
                Top Loss Diagnosis
              </span>
              <AlertOctagon className="h-4 w-4 text-red-400" />
            </div>
            <div className="text-sm font-bold text-red-400 capitalize truncate mt-1">
              {diagnostics.topMistake}
            </div>
            <span className="text-[11px] text-muted-foreground">
              Single highest leverage fix
            </span>
          </CardContent>
        </Card>

        {/* Rule Adherence */}
        <Card className="bg-card/70 border-border/40 backdrop-blur-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground uppercase font-semibold">
                Rule Adherence
              </span>
              <Brain className="h-4 w-4 text-purple-400" />
            </div>
            <div className="text-2xl font-black font-mono text-purple-400 mt-1">
              {diagnostics.adherenceRate}%
            </div>
            <span className="text-[11px] text-muted-foreground">
              Execution discipline rate
            </span>
          </CardContent>
        </Card>
      </div>

      {/* Main Journal Table Card */}
      <Card className="flex flex-col border-border/40 bg-card/70 backdrop-blur-sm shadow-sm">
        <CardHeader className="py-4 px-5 border-b border-border/40 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <CardTitle className="text-lg font-bold text-foreground">
              Audited Trade Journal
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">
              Systematic SMC entries with multi-timeframe bias and psychological diagnostic tags
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={exportCSV}
              className="h-8 text-xs gap-1.5 border-border/40 hover:bg-white/5"
              title="Export all trades with full 6-pillar diagnostic data to Excel"
            >
              <Download className="h-3.5 w-3.5" />
              Export Excel (Full)
            </Button>
            <Button
              size="sm"
              onClick={() => setIsAddOpen(true)}
              className="h-8 text-xs gap-1.5 bg-emerald-500 text-black hover:bg-emerald-400 font-bold shadow-sm"
            >
              <PlusCircle className="h-4 w-4" />
              Log New Trade
            </Button>
          </div>
        </CardHeader>

        {/* Filter Toolbar */}
        <div className="p-3 px-5 border-b border-border/30 bg-black/20 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Search */}
            <div className="relative flex items-center">
              <Search className="h-3.5 w-3.5 absolute left-2.5 text-muted-foreground pointer-events-none" />
              <input
                type="text"
                placeholder="Search symbol, notes, mistake…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 w-44 lg:w-56 pl-8 pr-2 text-xs bg-background/80 border border-border/40 rounded-md focus:outline-none focus:border-emerald-500/50"
              />
            </div>

            {/* Source Filter */}
            <select
              value={filterSource}
              onChange={(e) => setFilterSource(e.target.value)}
              className="h-8 px-2.5 text-xs bg-emerald-950/40 border border-emerald-500/30 rounded-md font-semibold text-emerald-300 focus:outline-none"
            >
              <option value="all">Source: All Records</option>
              <option value="paper">Source: Paper Trading</option>
              <option value="backtest">Source: Backtest</option>
              <option value="live">Source: Live MT5</option>
              <option value="manual_note">Source: Manual Notes</option>
            </select>

            {/* Session Filter */}
            <select
              value={filterSession}
              onChange={(e) => setFilterSession(e.target.value)}
              className="h-8 px-2 text-xs bg-background/80 border border-border/40 rounded-md capitalize"
            >
              <option value="all">All Sessions</option>
              <option value="london">London Session</option>
              <option value="ny">NY Session</option>
              <option value="asian">Asian Session</option>
            </select>

            {/* Setup Filter */}
            <select
              value={filterSetup}
              onChange={(e) => setFilterSetup(e.target.value)}
              className="h-8 px-2 text-xs bg-background/80 border border-border/40 rounded-md"
            >
              <option value="all">All Setups</option>
              {uniqueSetups.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>

            {/* Mistake Taxonomy Filter */}
            <select
              value={filterMistake}
              onChange={(e) => setFilterMistake(e.target.value)}
              className="h-8 px-2 text-xs bg-background/80 border border-border/40 rounded-md font-medium text-amber-300"
            >
              <option value="all">All Diagnoses</option>
              {uniqueMistakes.map((m) => (
                <option key={m} value={m}>
                  {m.replace(/_/g, " ")}
                </option>
              ))}
            </select>

            {/* Outcome Filter */}
            <select
              value={filterOutcome}
              onChange={(e) => setFilterOutcome(e.target.value)}
              className="h-8 px-2 text-xs bg-background/80 border border-border/40 rounded-md uppercase"
            >
              <option value="all">All Outcomes</option>
              <option value="win">WIN</option>
              <option value="loss">LOSS</option>
              <option value="breakeven">BREAKEVEN</option>
            </select>

            {(searchQuery ||
              filterSource !== "all" ||
              filterOutcome !== "all" ||
              filterSetup !== "all" ||
              filterSession !== "all" ||
              filterMistake !== "all") && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearFilters}
                className="h-8 text-xs gap-1 text-muted-foreground hover:text-foreground"
              >
                <FilterX className="h-3.5 w-3.5" />
                Reset
              </Button>
            )}
          </div>

          <div className="text-muted-foreground text-xs font-mono">
            Showing {filteredTrades.length} of {trades.length} trades
          </div>
        </div>

        {/* Table Content */}
        <CardContent className="p-0 overflow-x-auto">
          {isLoading ? (
            <div className="p-12 text-center text-muted-foreground text-sm">
              Loading trade journal records…
            </div>
          ) : filteredTrades.length === 0 ? (
            <div className="p-12 text-center text-muted-foreground text-sm space-y-2">
              <p>No trade entries found in journal matching criteria.</p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setIsAddOpen(true)}
                className="text-xs gap-1.5"
              >
                <PlusCircle className="h-3.5 w-3.5 text-emerald-400" />
                Log First Trade
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader className="bg-muted/40 sticky top-0 z-10 text-xs">
                <TableRow>
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => handleSort("openedAt")}
                  >
                    Opened {sortField === "openedAt" && <SortIcon />}
                  </TableHead>
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => handleSort("symbol")}
                  >
                    Instrument {sortField === "symbol" && <SortIcon />}
                  </TableHead>
                  <TableHead>Session & HTF Bias</TableHead>
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => handleSort("setupType")}
                  >
                    SMC Setup Pattern {sortField === "setupType" && <SortIcon />}
                  </TableHead>
                  <TableHead className="text-right">Entry / SL / TP</TableHead>
                  <TableHead
                    className="text-right cursor-pointer select-none"
                    onClick={() => handleSort("pointsCaptured")}
                  >
                    Gold Points {sortField === "pointsCaptured" && <SortIcon />}
                  </TableHead>
                  <TableHead
                    className="text-right cursor-pointer select-none"
                    onClick={() => handleSort("rMultiple")}
                  >
                    Result (R) {sortField === "rMultiple" && <SortIcon />}
                  </TableHead>
                  <TableHead>Mistake Diagnosis</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody className="text-xs font-medium">
                {paginatedTrades.map((t) => (
                  <TableRow
                    key={t.id}
                    className="hover:bg-white/[0.02] transition-colors border-b border-border/30"
                  >
                    {/* Opened At */}
                    <TableCell className="font-mono text-muted-foreground whitespace-nowrap">
                      {format(new Date(t.openedAt), "MMM dd, HH:mm")}
                    </TableCell>

                    {/* Instrument & Direction & Source */}
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-1.5 font-mono font-bold">
                          <span>{t.symbol}</span>
                          <span
                            className={`text-[10px] px-1.5 py-0.2 rounded font-bold uppercase ${
                              t.direction === "long"
                                ? "bg-emerald-500/10 text-emerald-400"
                                : "bg-red-500/10 text-red-400"
                            }`}
                          >
                            {t.direction}
                          </span>
                        </div>
                        <div>
                          {t.source === "backtest" ? (
                            <span className="text-[9px] px-1.5 py-0.5 rounded font-extrabold bg-purple-500/20 text-purple-300 border border-purple-500/30 tracking-wider">
                              BACKTEST
                            </span>
                          ) : t.source === "manual_note" ? (
                            <span className="text-[9px] px-1.5 py-0.5 rounded font-extrabold bg-amber-500/20 text-amber-300 border border-amber-500/30 tracking-wider">
                              MANUAL
                            </span>
                          ) : t.source === "live" ? (
                            <span className="text-[9px] px-1.5 py-0.5 rounded font-extrabold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 tracking-wider">
                              LIVE MT5
                            </span>
                          ) : (
                            <span className="text-[9px] px-1.5 py-0.5 rounded font-extrabold bg-blue-500/20 text-blue-300 border border-blue-500/30 tracking-wider">
                              PAPER TRADING
                            </span>
                          )}
                        </div>
                      </div>
                    </TableCell>

                    {/* Session & HTF Bias */}
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="capitalize text-foreground font-semibold">
                          {t.session}
                        </span>
                        <span className="text-[11px] text-cyan-400">
                          {t.htfBias ? `HTF: ${t.htfBias}` : "HTF: Bullish"}
                        </span>
                      </div>
                    </TableCell>

                    {/* Setup Pattern */}
                    <TableCell>
                      <div className="flex flex-col max-w-[200px] truncate">
                        <span className="text-foreground truncate font-medium">
                          {t.setupType}
                        </span>
                        <span className="text-[11px] text-muted-foreground">
                          {t.setupTimeframe || "M15"} • {t.confluence || "Double Stack"}
                        </span>
                      </div>
                    </TableCell>

                    {/* Entry / SL / TP */}
                    <TableCell className="text-right font-mono text-[11px] text-muted-foreground">
                      <div>${t.entryPrice.toFixed(1)}</div>
                      <div className="text-[10px]">
                        SL: <span className="text-red-400">${t.sl.toFixed(1)}</span>
                      </div>
                    </TableCell>

                    {/* Points Captured */}
                    <TableCell className="text-right font-mono font-bold">
                      <span
                        className={
                          (t.pointsCaptured || 0) >= 0 ? "text-emerald-400" : "text-red-400"
                        }
                      >
                        {(t.pointsCaptured || 0) >= 0 ? "+" : ""}
                        {t.pointsCaptured ? `${t.pointsCaptured.toFixed(1)} pts` : "—"}
                      </span>
                    </TableCell>

                    {/* Outcome & R */}
                    <TableCell className="text-right font-mono">
                      <div className="flex flex-col items-end">
                        <Badge
                          variant={
                            t.outcome === "win"
                              ? "default"
                              : t.outcome === "loss"
                              ? "destructive"
                              : "secondary"
                          }
                          className="text-[10px] px-1.5 py-0 uppercase"
                        >
                          {t.outcome}
                        </Badge>
                        <span
                          className={`font-black mt-0.5 ${
                            (t.rMultiple || 0) >= 0 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {t.rMultiple ? `${t.rMultiple >= 0 ? "+" : ""}${t.rMultiple}R` : "—"}
                        </span>
                      </div>
                    </TableCell>

                    {/* Mistake Diagnosis */}
                    <TableCell>
                      <span
                        className={`text-[11px] px-2 py-0.5 rounded capitalize font-medium ${
                          !t.mistakeType || t.mistakeType === "clean"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : "bg-red-500/15 text-red-300 border border-red-500/30"
                        }`}
                      >
                        {(t.mistakeType || "Clean").replace(/_/g, " ")}
                      </span>
                    </TableCell>

                    {/* Actions */}
                    <TableCell className="text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setSelectedTrade(t);
                            setIsDetailOpen(true);
                          }}
                          className="h-7 px-2 text-xs font-semibold hover:bg-white/10 text-cyan-400"
                        >
                          <SlidersHorizontal className="h-3.5 w-3.5 mr-1" />
                          Diagnose
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={deleteMutation.isPending}
                          onClick={() => deleteMutation.mutate(t.id)}
                          className="h-7 w-7 text-muted-foreground hover:text-red-400"
                          title="Delete trade"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>

        {/* Pagination Footer */}
        <div className="p-3 px-5 border-t border-border/30 bg-black/20 flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span>Rows per page:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="h-7 px-2 bg-background border border-border/40 rounded text-xs"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <span>
              Page {page} of {totalPages}
            </span>
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="icon"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="h-7 w-7"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="h-7 w-7"
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Modals */}
      <TradeDetailModal
        trade={selectedTrade}
        isOpen={isDetailOpen}
        onClose={() => {
          setIsDetailOpen(false);
          setSelectedTrade(null);
        }}
      />

      <AddTradeModal
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
      />
    </div>
  );
}
