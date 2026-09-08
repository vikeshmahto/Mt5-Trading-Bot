import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateTrade } from "@/lib/api";
import { Trade } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  X,
  Target,
  Compass,
  Zap,
  Activity,
  Award,
  Brain,
  FileEdit,
  Save,
  Clock,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";
import { format } from "date-fns";

interface TradeDetailModalProps {
  trade: Trade | null;
  isOpen: boolean;
  onClose: () => void;
}

export function TradeDetailModal({
  trade,
  isOpen,
  onClose,
}: TradeDetailModalProps) {
  const queryClient = useQueryClient();

  const [biasCorrect, setBiasCorrect] = useState<"yes" | "no" | "partial">(
    trade?.biasCorrect || "yes"
  );
  const [ruleAdherence, setRuleAdherence] = useState(
    trade?.ruleAdherence || "followed_rules"
  );
  const [emotionalState, setEmotionalState] = useState(
    trade?.emotionalState || "calm"
  );
  const [mistakeType, setMistakeType] = useState(trade?.mistakeType || "clean");
  const [textbookComparison, setTextbookComparison] = useState(
    trade?.textbookComparison || ""
  );
  const [reviewNotes, setReviewNotes] = useState(trade?.reviewNotes || "");
  const [screenshotUrl, setScreenshotUrl] = useState(
    trade?.screenshotUrl || ""
  );

  useEffect(() => {
    if (trade) {
      setBiasCorrect(trade.biasCorrect || "yes");
      setRuleAdherence(trade.ruleAdherence || "followed_rules");
      setEmotionalState(trade.emotionalState || "calm");
      setMistakeType(trade.mistakeType || "clean");
      setTextbookComparison(trade.textbookComparison || "");
      setReviewNotes(trade.reviewNotes || "");
      setScreenshotUrl(trade.screenshotUrl || "");
    }
  }, [trade]);

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!trade) throw new Error("No trade selected");
      return updateTrade(trade.id, {
        biasCorrect,
        ruleAdherence,
        emotionalState,
        mistakeType,
        textbookComparison,
        reviewNotes,
        screenshotUrl,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trades"] });
      toast.success("Trade review & diagnostic tags updated");
      onClose();
    },
    onError: (err: any) => {
      toast.error(`Failed to save review: ${err.message}`);
    },
  });

  if (!isOpen || !trade) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 overflow-y-auto">
      <div className="relative w-full max-w-4xl bg-card border border-border/60 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border/40 bg-gradient-to-r from-card to-background">
          <div className="flex items-center gap-3">
            <div
              className={`h-10 w-10 rounded-xl flex items-center justify-center font-black text-sm uppercase ${
                trade.direction === "long"
                  ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                  : "bg-red-500/15 text-red-400 border border-red-500/30"
              }`}
            >
              {trade.direction}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-black text-foreground tracking-tight">
                  {trade.symbol} — {trade.setupType}
                </h2>
                <Badge
                  variant={
                    trade.outcome === "win"
                      ? "default"
                      : trade.outcome === "loss"
                      ? "destructive"
                      : "secondary"
                  }
                  className="font-mono text-xs uppercase"
                >
                  {trade.outcome || "OPEN"}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground flex items-center gap-2 mt-0.5">
                <Clock className="h-3 w-3" />
                {trade.openedAt
                  ? format(new Date(trade.openedAt), "MMM dd, yyyy HH:mm")
                  : "N/A"}{" "}
                • Session:{" "}
                <span className="capitalize font-semibold text-foreground">
                  {trade.session}
                </span>{" "}
                • ID: <span className="font-mono">{trade.id}</span>
              </p>
            </div>
          </div>

          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Pillar 1 & 2: Context / Bias & Setup Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* 1. Context / Bias */}
            <div className="p-4 rounded-xl border border-border/40 bg-background/50 space-y-3">
              <div className="flex items-center gap-2 text-sm font-bold text-cyan-400">
                <Compass className="h-4 w-4" />
                1. Context & Higher Timeframe Bias
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-muted-foreground block">HTF Bias</span>
                  <span className="font-semibold text-foreground uppercase">
                    {trade.htfBias || "Bullish (Structure)"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">
                    HTF Key Levels / Reason
                  </span>
                  <span className="text-foreground">
                    {trade.htfReason || "Daily demand tap + 4H BOS"}
                  </span>
                </div>
              </div>

              <div className="pt-2 border-t border-border/20">
                <label className="text-xs font-medium text-muted-foreground block mb-1">
                  Was HTF Bias Correct in Hindsight?
                </label>
                <div className="flex gap-2">
                  {(["yes", "no", "partial"] as const).map((opt) => (
                    <button
                      key={opt}
                      onClick={() => setBiasCorrect(opt)}
                      className={`flex-1 py-1.5 px-2 text-xs font-semibold rounded-md border capitalize transition-all ${
                        biasCorrect === opt
                          ? "bg-cyan-500/20 border-cyan-500/50 text-cyan-300"
                          : "border-border/40 text-muted-foreground hover:bg-white/5"
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* 2. Setup & Confluence */}
            <div className="p-4 rounded-xl border border-border/40 bg-background/50 space-y-3">
              <div className="flex items-center gap-2 text-sm font-bold text-amber-400">
                <Zap className="h-4 w-4" />
                2. Setup Pattern & Confluence
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-muted-foreground block">Trigger Pattern</span>
                  <span className="font-semibold text-foreground">
                    {trade.setupType}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Setup Timeframe</span>
                  <span className="font-mono text-foreground">
                    {trade.setupTimeframe || "M15 / H1"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Confluence Stacking</span>
                  <span className="font-medium text-foreground capitalize">
                    {trade.confluence || "Double (Sweep + OB)"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Planned R:R</span>
                  <span className="font-mono font-bold text-emerald-400">
                    {trade.plannedRr ? `${trade.plannedRr}:1` : "1:3.0"}
                  </span>
                </div>
              </div>

              <div className="pt-2 border-t border-border/20">
                <label className="text-xs font-medium text-muted-foreground block mb-1">
                  Setup Chart Screenshot URL
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={screenshotUrl}
                    onChange={(e) => setScreenshotUrl(e.target.value)}
                    placeholder="https://tradingview.com/x/... or image link"
                    className="flex-1 text-xs px-2.5 py-1.5 rounded bg-black/40 border border-border/40 focus:outline-none focus:border-amber-500/50"
                  />
                  {screenshotUrl && (
                    <a
                      href={screenshotUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 bg-white/5 hover:bg-white/10 rounded text-muted-foreground hover:text-foreground"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Pillar 3 & 4: Execution Precision & Outcome / Excursion */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* 3. Execution */}
            <div className="p-4 rounded-xl border border-border/40 bg-background/50 space-y-3">
              <div className="flex items-center gap-2 text-sm font-bold text-purple-400">
                <Target className="h-4 w-4" />
                3. Execution Precision & Risk
              </div>
              <div className="grid grid-cols-3 gap-3 text-xs font-mono">
                <div>
                  <span className="text-muted-foreground block text-[11px]">Entry Price</span>
                  <span className="font-semibold text-foreground">
                    ${trade.entryPrice.toFixed(2)}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[11px]">Stop Loss</span>
                  <span className="text-red-400 font-semibold">
                    ${trade.sl.toFixed(2)}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[11px]">Take Profit</span>
                  <span className="text-emerald-400 font-semibold">
                    ${trade.tp.toFixed(2)}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs pt-1">
                <div>
                  <span className="text-muted-foreground block">Entry Timeframe</span>
                  <span className="font-medium text-foreground">
                    {trade.entryTimeframe || "M1 Refinement"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Entry Trigger</span>
                  <span className="font-medium text-foreground">
                    {trade.entryTrigger || "Clean Retest on FVG"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">SL Logic</span>
                  <span className="font-medium text-foreground">
                    {trade.slLogic || "Structure Invalidation"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">Risk % Account</span>
                  <span className="font-mono font-bold text-amber-400">
                    {trade.riskPct || 1.0}%
                  </span>
                </div>
              </div>
            </div>

            {/* 4. Outcome & Excursion */}
            <div className="p-4 rounded-xl border border-border/40 bg-background/50 space-y-3">
              <div className="flex items-center gap-2 text-sm font-bold text-emerald-400">
                <Award className="h-4 w-4" />
                4. Outcome & MAE / MFE Excursion
              </div>
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div className="p-2 rounded bg-black/40 border border-border/20 text-center">
                  <span className="text-muted-foreground block text-[10px] uppercase">
                    Result (R)
                  </span>
                  <span
                    className={`text-lg font-black font-mono ${
                      (trade.rMultiple || 0) >= 0
                        ? "text-emerald-400"
                        : "text-red-400"
                    }`}
                  >
                    {trade.rMultiple
                      ? `${trade.rMultiple >= 0 ? "+" : ""}${trade.rMultiple.toFixed(2)}R`
                      : "N/A"}
                  </span>
                </div>

                <div className="p-2 rounded bg-black/40 border border-border/20 text-center">
                  <span className="text-muted-foreground block text-[10px] uppercase">
                    Gold Points
                  </span>
                  <span className="text-lg font-black font-mono text-foreground">
                    {trade.pointsCaptured
                      ? `${trade.pointsCaptured.toFixed(1)} pts`
                      : "~10.0 pts"}
                  </span>
                </div>

                <div className="p-2 rounded bg-black/40 border border-border/20 text-center">
                  <span className="text-muted-foreground block text-[10px] uppercase">
                    Exit Price
                  </span>
                  <span className="text-lg font-black font-mono text-foreground">
                    {trade.exitPrice ? `$${trade.exitPrice.toFixed(2)}` : "—"}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs pt-1">
                <div>
                  <span className="text-muted-foreground block">
                    MAE (Max Adverse Excursion)
                  </span>
                  <span className="font-mono text-amber-400">
                    {trade.mae ? `${trade.mae} pts (Drawdown)` : "1.8 pts (Clean)"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">
                    MFE (Max Favorable Excursion)
                  </span>
                  <span className="font-mono text-emerald-400">
                    {trade.mfe ? `${trade.mfe} pts (Max Run)` : "12.4 pts"}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Pillar 5 & 6: Process / Psychology & Post-Trade Review */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* 5. Psychology & Rules */}
            <div className="p-4 rounded-xl border border-border/40 bg-background/50 space-y-3">
              <div className="flex items-center gap-2 text-sm font-bold text-pink-400">
                <Brain className="h-4 w-4" />
                5. Process & Psychology Diagnostics
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">
                  Rule Adherence
                </label>
                <select
                  value={ruleAdherence}
                  onChange={(e) => setRuleAdherence(e.target.value)}
                  className="w-full text-xs p-2 rounded bg-black/40 border border-border/40 text-foreground focus:outline-none focus:border-pink-500/50"
                >
                  <option value="followed_rules">Followed Rules Exactly</option>
                  <option value="early_entry">Entered Early (Anticipated)</option>
                  <option value="chased">Chased Entry (Late)</option>
                  <option value="moved_sl">Moved Stop Loss</option>
                  <option value="closed_early">Closed Early (Fear / Greed)</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">
                  Emotional State
                </label>
                <div className="grid grid-cols-3 gap-1.5">
                  {(["calm", "confident", "fomo", "revenge", "tilted"] as const).map(
                    (emo) => (
                      <button
                        key={emo}
                        type="button"
                        onClick={() => setEmotionalState(emo)}
                        className={`py-1 px-2 text-xs font-medium rounded border capitalize transition-colors ${
                          emotionalState === emo
                            ? "bg-pink-500/20 border-pink-500/50 text-pink-300 font-bold"
                            : "border-border/30 text-muted-foreground hover:bg-white/5"
                        }`}
                      >
                        {emo}
                      </button>
                    )
                  )}
                </div>
              </div>
            </div>

            {/* 6. Post-Trade Review & Mistake Taxonomy */}
            <div className="p-4 rounded-xl border border-border/40 bg-background/50 space-y-3">
              <div className="flex items-center gap-2 text-sm font-bold text-red-400">
                <FileEdit className="h-4 w-4" />
                6. Post-Trade Review & Mistake Taxonomy
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">
                  Mistake Classification Tag (Single Highest Leverage Field)
                </label>
                <select
                  value={mistakeType}
                  onChange={(e) => setMistakeType(e.target.value)}
                  className="w-full text-xs p-2 rounded bg-black/40 border border-border/40 text-foreground focus:outline-none focus:border-red-500/50 font-semibold"
                >
                  <option value="clean">Clean Trade (No Mistake / Cost of Business)</option>
                  <option value="wrong_bias">Wrong HTF Bias</option>
                  <option value="bad_entry_timing">Bad Entry Timing / Chased</option>
                  <option value="ignored_htf">Ignored HTF Structure</option>
                  <option value="sized_wrong">Sized Wrong / Overleveraged</option>
                  <option value="moved_sl">Moved Stop Loss / Impatient</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">
                  Textbook Entry vs What You Took
                </label>
                <input
                  type="text"
                  value={textbookComparison}
                  onChange={(e) => setTextbookComparison(e.target.value)}
                  placeholder="Textbook waited for 1min displacement; I jumped on first touch..."
                  className="w-full text-xs p-2 rounded bg-black/40 border border-border/40 text-foreground focus:outline-none focus:border-red-500/50"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">
                  Lessons Learned & Key Takeaway
                </label>
                <textarea
                  rows={2}
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="Takeaways for backtester & future discretionary setups..."
                  className="w-full text-xs p-2 rounded bg-black/40 border border-border/40 text-foreground focus:outline-none focus:border-red-500/50 resize-none"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-border/40 bg-card/60 flex items-center justify-between">
          <div className="text-xs text-muted-foreground flex items-center gap-1.5">
            <AlertCircle className="h-3.5 w-3.5 text-cyan-400" />
            Updating review tags syncs directly to the quant backtest database.
          </div>

          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
              className="bg-emerald-500 text-black hover:bg-emerald-400 gap-1.5 font-bold"
            >
              <Save className="h-4 w-4" />
              {saveMutation.isPending ? "Saving..." : "Save Trade Review"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
