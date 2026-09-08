import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createTrade } from "@/lib/api";
import { Trade, Direction, Session, Outcome } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { X, PlusCircle, Compass, Zap, Target, Award, Brain } from "lucide-react";
import { toast } from "sonner";

interface AddTradeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AddTradeModal({ isOpen, onClose }: AddTradeModalProps) {
  const queryClient = useQueryClient();

  const [symbol, setSymbol] = useState("XAUUSD");
  const [direction, setDirection] = useState<Direction>("long");
  const [session, setSession] = useState<Session>("london");
  const [entryPrice, setEntryPrice] = useState<number>(4430.0);
  const [exitPrice, setExitPrice] = useState<number>(4440.0);
  const [sl, setSl] = useState<number>(4425.0);
  const [tp, setTp] = useState<number>(4445.0);
  const [outcome, setOutcome] = useState<Outcome>("win");
  const [setupType, setSetupType] = useState("Liquidity Sweep + OB");
  const [setupTimeframe, setSetupTimeframe] = useState("M15");
  const [htfBias, setHtfBias] = useState<"bullish" | "bearish" | "range">("bullish");
  const [htfReason, setHtfReason] = useState("Daily demand reaction + 4H swing break");
  const [entryTimeframe, setEntryTimeframe] = useState("M1");
  const [entryTrigger, setEntryTrigger] = useState("Clean FVG Retest");
  const [slLogic, setSlLogic] = useState("Structure (Sweep Low)");
  const [riskPct, setRiskPct] = useState(1.0);
  const [pointsCaptured, setPointsCaptured] = useState(10.0);
  const [ruleAdherence, setRuleAdherence] = useState("followed_rules");
  const [emotionalState, setEmotionalState] = useState("calm");
  const [mistakeType, setMistakeType] = useState("clean");
  const [reviewNotes, setReviewNotes] = useState("");

  const createMutation = useMutation({
    mutationFn: () => {
      const risk = Math.abs(entryPrice - sl);
      const rMult = risk > 0 ? (outcome === "win" ? pointsCaptured / risk : -1.0) : 0;
      
      const payload: Partial<Trade> = {
        symbol: symbol.toUpperCase(),
        direction,
        session,
        entryPrice,
        exitPrice,
        sl,
        tp,
        rMultiple: Number(rMult.toFixed(2)),
        outcome,
        setupType,
        setupTimeframe,
        htfBias,
        htfReason,
        entryTimeframe,
        entryTrigger,
        slLogic,
        riskPct,
        pointsCaptured,
        ruleAdherence,
        emotionalState,
        mistakeType,
        reviewNotes,
        source: "manual_note",
        openedAt: new Date().toISOString(),
        closedAt: new Date().toISOString(),
      };
      return createTrade(payload);
    },
    onSuccess: (newTrade) => {
      queryClient.invalidateQueries({ queryKey: ["trades"] });
      toast.success(`Trade ${newTrade.id} logged successfully!`);
      onClose();
    },
    onError: (err: any) => {
      toast.error(`Failed to log trade: ${err.message}`);
    },
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 overflow-y-auto">
      <div className="relative w-full max-w-3xl bg-card border border-border/60 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border/40 bg-gradient-to-r from-card to-background">
          <div className="flex items-center gap-2.5">
            <PlusCircle className="h-5 w-5 text-emerald-400" />
            <div>
              <h2 className="text-lg font-black text-foreground">Log New SMC Trade</h2>
              <p className="text-xs text-muted-foreground">
                Record discretionary or systematic setups with full diagnostic tags
              </p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-5 w-5 text-muted-foreground hover:text-foreground" />
          </Button>
        </div>

        {/* Scrollable Form */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 text-xs">
          {/* Section 1: Instrument, Direction, Session */}
          <div className="p-3.5 rounded-lg border border-border/40 bg-background/50 space-y-3">
            <div className="font-bold text-foreground flex items-center gap-1.5 text-xs text-cyan-400">
              <Compass className="h-3.5 w-3.5" /> 1. Instrument & HTF Context
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-muted-foreground block mb-1">Instrument</label>
                <select
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40 font-bold"
                >
                  <option value="XAUUSD">XAUUSD (Gold)</option>
                  <option value="BTCUSD">BTCUSD (Bitcoin)</option>
                  <option value="EURUSD">EURUSD</option>
                  <option value="GBPUSD">GBPUSD</option>
                </select>
              </div>

              <div>
                <label className="text-muted-foreground block mb-1">Direction</label>
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    onClick={() => setDirection("long")}
                    className={`flex-1 p-2 rounded font-bold uppercase transition-all ${
                      direction === "long"
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/50"
                        : "border border-border/30 text-muted-foreground"
                    }`}
                  >
                    LONG
                  </button>
                  <button
                    type="button"
                    onClick={() => setDirection("short")}
                    className={`flex-1 p-2 rounded font-bold uppercase transition-all ${
                      direction === "short"
                        ? "bg-red-500/20 text-red-400 border border-red-500/50"
                        : "border border-border/30 text-muted-foreground"
                    }`}
                  >
                    SHORT
                  </button>
                </div>
              </div>

              <div>
                <label className="text-muted-foreground block mb-1">Session</label>
                <select
                  value={session}
                  onChange={(e) => setSession(e.target.value as Session)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40 capitalize"
                >
                  <option value="london">London Session</option>
                  <option value="ny">New York Session</option>
                  <option value="asian">Asian Session</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <div>
                <label className="text-muted-foreground block mb-1">HTF Bias (1D / 4H / 1H)</label>
                <select
                  value={htfBias}
                  onChange={(e) => setHtfBias(e.target.value as any)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40 capitalize font-medium"
                >
                  <option value="bullish">Bullish (Structure / Key Level)</option>
                  <option value="bearish">Bearish (Structure / Key Level)</option>
                  <option value="range">Range / Neutral</option>
                </select>
              </div>
              <div>
                <label className="text-muted-foreground block mb-1">HTF Rationale</label>
                <input
                  type="text"
                  value={htfReason}
                  onChange={(e) => setHtfReason(e.target.value)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40"
                />
              </div>
            </div>
          </div>

          {/* Section 2: Setup Pattern */}
          <div className="p-3.5 rounded-lg border border-border/40 bg-background/50 space-y-3">
            <div className="font-bold text-foreground flex items-center gap-1.5 text-xs text-amber-400">
              <Zap className="h-3.5 w-3.5" /> 2. SMC Setup Pattern & Confluence
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-muted-foreground block mb-1">Setup Pattern</label>
                <select
                  value={setupType}
                  onChange={(e) => setSetupType(e.target.value)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40 font-semibold"
                >
                  <option value="Liquidity Sweep">Liquidity Sweep</option>
                  <option value="Order Block Retest">Order Block Retest</option>
                  <option value="FVG Retest">FVG Retest</option>
                  <option value="OB+FVG confluence">OB + FVG Confluence</option>
                  <option value="Liquidity Sweep + OB">Sweep + OB Confluence</option>
                  <option value="Triple Stack (Sweep + OB + FVG)">Triple Stack (Sweep + OB + FVG)</option>
                </select>
              </div>
              <div>
                <label className="text-muted-foreground block mb-1">Setup Formation Timeframe</label>
                <select
                  value={setupTimeframe}
                  onChange={(e) => setSetupTimeframe(e.target.value)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40 font-mono"
                >
                  <option value="M15">M15 Timeframe</option>
                  <option value="H1">H1 Timeframe</option>
                  <option value="H4">H4 Timeframe</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 3: Execution & Pricing */}
          <div className="p-3.5 rounded-lg border border-border/40 bg-background/50 space-y-3">
            <div className="font-bold text-foreground flex items-center gap-1.5 text-xs text-purple-400">
              <Target className="h-3.5 w-3.5" /> 3. Execution & Price Levels
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
              <div>
                <label className="text-muted-foreground block mb-1">Entry Price</label>
                <input
                  type="number"
                  step="0.1"
                  value={entryPrice}
                  onChange={(e) => setEntryPrice(parseFloat(e.target.value) || 0)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40"
                />
              </div>
              <div>
                <label className="text-muted-foreground block mb-1">Stop Loss</label>
                <input
                  type="number"
                  step="0.1"
                  value={sl}
                  onChange={(e) => setSl(parseFloat(e.target.value) || 0)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40 text-red-400"
                />
              </div>
              <div>
                <label className="text-muted-foreground block mb-1">Take Profit</label>
                <input
                  type="number"
                  step="0.1"
                  value={tp}
                  onChange={(e) => setTp(parseFloat(e.target.value) || 0)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40 text-emerald-400"
                />
              </div>
              <div>
                <label className="text-muted-foreground block mb-1">Exit Price</label>
                <input
                  type="number"
                  step="0.1"
                  value={exitPrice}
                  onChange={(e) => setExitPrice(parseFloat(e.target.value) || 0)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
              <div>
                <label className="text-muted-foreground block mb-1">Entry Refinement TF</label>
                <select
                  value={entryTimeframe}
                  onChange={(e) => setEntryTimeframe(e.target.value)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40"
                >
                  <option value="M1">M1 (1-minute entry)</option>
                  <option value="M5">M5 (5-minute entry)</option>
                </select>
              </div>
              <div>
                <label className="text-muted-foreground block mb-1">Entry Trigger</label>
                <select
                  value={entryTrigger}
                  onChange={(e) => setEntryTrigger(e.target.value)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40"
                >
                  <option value="Clean FVG Retest">Clean FVG Retest</option>
                  <option value="Chased / Market">Chased / Market Entry</option>
                  <option value="Limit at OB Confluence">Limit at OB Confluence</option>
                </select>
              </div>
              <div>
                <label className="text-muted-foreground block mb-1">SL Logic</label>
                <select
                  value={slLogic}
                  onChange={(e) => setSlLogic(e.target.value)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40"
                >
                  <option value="Structure (Sweep Low)">Structure (Sweep Low/High)</option>
                  <option value="ATR Buffer">ATR Buffer</option>
                  <option value="Invalidation of FVG">Invalidation of FVG</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 4: Outcome & Points */}
          <div className="p-3.5 rounded-lg border border-border/40 bg-background/50 space-y-3">
            <div className="font-bold text-foreground flex items-center gap-1.5 text-xs text-emerald-400">
              <Award className="h-3.5 w-3.5" /> 4. Outcome & Gold Points Captured
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-muted-foreground block mb-1">Outcome</label>
                <select
                  value={outcome}
                  onChange={(e) => setOutcome(e.target.value as Outcome)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40 font-bold uppercase"
                >
                  <option value="win">WIN</option>
                  <option value="loss">LOSS</option>
                  <option value="breakeven">BREAKEVEN</option>
                </select>
              </div>

              <div>
                <label className="text-muted-foreground block mb-1">
                  Points Captured (vs 10pt Target)
                </label>
                <input
                  type="number"
                  step="0.5"
                  value={pointsCaptured}
                  onChange={(e) => setPointsCaptured(parseFloat(e.target.value) || 0)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40 font-mono font-bold"
                />
              </div>

              <div>
                <label className="text-muted-foreground block mb-1">Account Risk %</label>
                <input
                  type="number"
                  step="0.1"
                  value={riskPct}
                  onChange={(e) => setRiskPct(parseFloat(e.target.value) || 1.0)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40 font-mono font-bold text-amber-400"
                />
              </div>
            </div>
          </div>

          {/* Section 5 & 6: Psychology & Mistake Taxonomy */}
          <div className="p-3.5 rounded-lg border border-border/40 bg-background/50 space-y-3">
            <div className="font-bold text-foreground flex items-center gap-1.5 text-xs text-pink-400">
              <Brain className="h-3.5 w-3.5" /> 5 & 6. Psychology & Mistake Classification
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-muted-foreground block mb-1">Rule Adherence</label>
                <select
                  value={ruleAdherence}
                  onChange={(e) => setRuleAdherence(e.target.value)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40"
                >
                  <option value="followed_rules">Followed Rules Exactly</option>
                  <option value="early_entry">Entered Early</option>
                  <option value="chased">Chased Entry</option>
                  <option value="moved_sl">Moved SL</option>
                  <option value="closed_early">Closed Early</option>
                </select>
              </div>

              <div>
                <label className="text-muted-foreground block mb-1">Emotional State</label>
                <select
                  value={emotionalState}
                  onChange={(e) => setEmotionalState(e.target.value)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40 capitalize"
                >
                  <option value="calm">Calm</option>
                  <option value="confident">Confident</option>
                  <option value="fomo">FOMO</option>
                  <option value="revenge">Revenge</option>
                  <option value="tilted">Tilted</option>
                </select>
              </div>

              <div>
                <label className="text-muted-foreground block mb-1">Mistake Classification</label>
                <select
                  value={mistakeType}
                  onChange={(e) => setMistakeType(e.target.value)}
                  className="w-full p-2 rounded bg-black/40 border border-border/40 font-semibold"
                >
                  <option value="clean">Clean (No Mistake)</option>
                  <option value="wrong_bias">Wrong HTF Bias</option>
                  <option value="bad_entry_timing">Bad Entry Timing</option>
                  <option value="ignored_htf">Ignored HTF Structure</option>
                  <option value="sized_wrong">Sized Wrong</option>
                  <option value="moved_sl">Moved SL</option>
                </select>
              </div>
            </div>

            <div>
              <label className="text-muted-foreground block mb-1">Takeaways & Review Notes</label>
              <textarea
                rows={2}
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="What was clean about this trade or what to avoid in next backtest..."
                className="w-full p-2 rounded bg-black/40 border border-border/40 resize-none text-xs"
              />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border/40 bg-card/60 flex items-center justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            size="sm"
            disabled={createMutation.isPending}
            onClick={() => createMutation.mutate()}
            className="bg-emerald-500 text-black hover:bg-emerald-400 font-bold"
          >
            {createMutation.isPending ? "Logging..." : "Log Trade to Journal"}
          </Button>
        </div>
      </div>
    </div>
  );
}
