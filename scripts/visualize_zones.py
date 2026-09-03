"""
Interactive SMC Visual Debugger using Plotly (scripts/visualize_zones.py)

Visualizes:
1. Candlestick Price Action (M15 bars).
2. Order Block (OB) Zones (Bullish blue/cyan, Bearish orange/magenta).
3. Fair Value Gap (FVG) Zones (Bullish green, Bearish red/coral).
4. Liquidity Sweeps (High/Low sweep markers).
5. Historical Trades (Entries, Exits, Win/Loss colored lines, SL/TP references).
6. ADX & Market Regime subpanel showing Choppy (<20) vs Trending (>=25) background.

Usage:
    python scripts/visualize_zones.py --symbol XAUUSD --start 2026-03-02 --end 2026-03-12
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.logger import get_logger
from core.types import Direction
from signals.fvg import detect_fvgs
from signals.liquidity_sweep import detect_liquidity_sweeps
from signals.order_blocks import detect_order_blocks
from signals.regime import calculate_adx_series, detect_market_regime, MarketRegime

log = get_logger("scripts.visualize_zones")


def create_zone_visualization(
    symbol: str = "XAUUSD",
    start_date: str = "2026-03-02",
    end_date: str = "2026-03-12",
    trades_csv: str = "reports/pristine_holdout_spring2026_XAUUSD_trades.csv",
    output_html: str = "reports/visualizations/xauusd_spring2026_chop_debug.html",
):
    print(f"\n====================================================================")
    print(f"GENERATING PLOTLY SMC VISUALIZATION: {symbol} [{start_date} to {end_date}]")
    print(f"====================================================================")

    # 1. Load data from cache
    cache_dir = Path("data/cache")
    m15_file = cache_dir / f"{symbol}_M15.parquet"
    h1_file = cache_dir / f"{symbol}_H1.parquet"
    h4_file = cache_dir / f"{symbol}_H4.parquet"
    d1_file = cache_dir / f"{symbol}_D1.parquet"

    if not m15_file.exists():
        raise FileNotFoundError(f"Missing cached data: {m15_file}")

    m15_full = pd.read_parquet(m15_file)
    h1_full = pd.read_parquet(h1_file) if h1_file.exists() else pd.DataFrame()
    h4_full = pd.read_parquet(h4_file) if h4_file.exists() else pd.DataFrame()
    d1_full = pd.read_parquet(d1_file) if d1_file.exists() else pd.DataFrame()

    m15_df = m15_full.loc[start_date:end_date].copy()
    if m15_df.empty:
        raise ValueError(f"No M15 bars found in range {start_date} to {end_date}")

    print(f"Loaded {len(m15_df)} M15 bars from {m15_df.index[0]} to {m15_df.index[-1]}")

    # 2. Detect SMC Zones across the slice
    obs = detect_order_blocks(m15_df, timeframe="M15")
    fvgs = detect_fvgs(m15_df, timeframe="M15")
    sweeps = detect_liquidity_sweeps(m15_df, timeframe="M15")

    print(f"Detected: {len(obs)} Order Blocks | {len(fvgs)} FVGs | {len(sweeps)} Liquidity Sweeps")

    # 3. Calculate ADX and Regime
    m15_adx = calculate_adx_series(m15_df, length=14)
    h4_slice = h4_full.loc[:end_date] if not h4_full.empty else pd.DataFrame()
    h4_adx = calculate_adx_series(h4_slice, length=14) if not h4_slice.empty else pd.DataFrame()

    # 4. Load Trades if available
    trades_df = pd.DataFrame()
    if os.path.exists(trades_csv):
        raw_trades = pd.read_csv(trades_csv)
        raw_trades["entry_time"] = pd.to_datetime(raw_trades["entry_time"])
        raw_trades["exit_time"] = pd.to_datetime(raw_trades["exit_time"])
        
        # Filter trades that overlap with our view window
        mask = (raw_trades["entry_time"] >= pd.Timestamp(start_date, tz="UTC")) & (
            raw_trades["entry_time"] <= pd.Timestamp(end_date + " 23:59:59", tz="UTC")
        )
        trades_df = raw_trades[mask].copy()
        print(f"Found {len(trades_df)} trades in range ({len(raw_trades)} total in CSV)")
    else:
        print(f"Note: Trades CSV {trades_csv} not found, displaying zones only.")

    # 5. Build Subplots (Row 1: Price Action & SMC Zones, Row 2: ADX & Regime)
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=[
            f"{symbol} M15 — SMC Structure, Order Blocks, FVGs & Fakeout Analysis",
            "Directional Momentum (ADX 14) & Regime State",
        ],
        row_heights=[0.78, 0.22],
    )

    # Candlestick Trace
    fig.add_trace(
        go.Candlestick(
            x=m15_df.index,
            open=m15_df["open"],
            high=m15_df["high"],
            low=m15_df["low"],
            close=m15_df["close"],
            name="M15 Price",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
            increasing_fillcolor="#26a69a",
            decreasing_fillcolor="#ef5350",
        ),
        row=1,
        col=1,
    )

    # 6. Add FVG Zones
    for fvg in fvgs:
        is_bull = (fvg.direction == Direction.BULLISH)
        fill_color = "rgba(46, 204, 113, 0.20)" if is_bull else "rgba(231, 76, 60, 0.20)"
        line_color = "rgba(46, 204, 113, 0.65)" if is_bull else "rgba(231, 76, 60, 0.65)"
        fvg_type = "Bull FVG" if is_bull else "Bear FVG"

        # End box either when retested or end of slice
        box_end = fvg.retested_at if fvg.retested_at and fvg.retested_at <= m15_df.index[-1] else m15_df.index[-1]

        fig.add_shape(
            type="rect",
            x0=fvg.timestamp,
            x1=box_end,
            y0=fvg.bottom,
            y1=fvg.top,
            fillcolor=fill_color,
            line=dict(color=line_color, width=1, dash="dot"),
            row=1,
            col=1,
        )

    # 7. Add Order Block (OB) Zones
    for ob in obs:
        is_bull = (ob.direction == Direction.BULLISH)
        fill_color = "rgba(52, 152, 219, 0.22)" if is_bull else "rgba(230, 126, 34, 0.22)"
        line_color = "rgba(52, 152, 219, 0.75)" if is_bull else "rgba(230, 126, 34, 0.75)"
        ob_type = "Bullish OB" if is_bull else "Bearish OB"

        box_end = ob.mitigated_at if ob.mitigated_at and ob.mitigated_at <= m15_df.index[-1] else m15_df.index[-1]

        fig.add_shape(
            type="rect",
            x0=ob.timestamp,
            x1=box_end,
            y0=ob.low,
            y1=ob.high,
            fillcolor=fill_color,
            line=dict(color=line_color, width=1.2),
            row=1,
            col=1,
        )

    # 8. Add Liquidity Sweeps
    if sweeps:
        sweep_times = [s.timestamp for s in sweeps if s.timestamp in m15_df.index]
        sweep_prices = [s.swept_level for s in sweeps if s.timestamp in m15_df.index]
        sweep_texts = [
            f"Sweep: {s.direction.value} | Level={s.swept_level:.2f} | Disp={s.displacement:.2f}"
            for s in sweeps if s.timestamp in m15_df.index
        ]
        if sweep_times:
            fig.add_trace(
                go.Scatter(
                    x=sweep_times,
                    y=sweep_prices,
                    mode="markers",
                    marker=dict(
                        symbol="diamond",
                        size=9,
                        color="#f1c40f",
                        line=dict(color="#ffffff", width=1),
                    ),
                    name="Liquidity Sweep",
                    text=sweep_texts,
                    hoverinfo="text+x+y",
                ),
                row=1,
                col=1,
            )

    # 9. Add Historical Trades Overlaid on Candlesticks
    if not trades_df.empty:
        for _, trade in trades_df.iterrows():
            is_win = trade["pnl_usd"] > 0
            trade_color = "#00e676" if is_win else "#ff1744"
            outcome_label = "WIN (TP Hit)" if is_win else "LOSS (SL Hit / Fakeout)"
            direction_arrow = "▲" if trade["direction"] == "bullish" else "▼"

            hover_text = (
                f"<b>Trade #{int(trade['trade_no'])}: {trade['direction'].upper()} {trade['signal_type']}</b><br>"
                f"Outcome: <span style='color:{trade_color}'><b>{outcome_label}</b></span><br>"
                f"Score: {trade['confluence_score']:.0f} | PnL: ${trade['pnl_usd']:+.2f} ({trade['pnl_r']:+.2f}R)<br>"
                f"Entry: {trade['entry_price']:.2f} @ {trade['entry_time']}<br>"
                f"Exit: {trade['exit_price']:.2f} @ {trade['exit_time']}<br>"
                f"SL: {trade['stop_loss']:.2f} | TP: {trade['take_profit']:.2f}"
            )

            # Trade execution trajectory line
            fig.add_trace(
                go.Scatter(
                    x=[trade["entry_time"], trade["exit_time"]],
                    y=[trade["entry_price"], trade["exit_price"]],
                    mode="lines+markers",
                    line=dict(color=trade_color, width=2.2, dash="solid" if is_win else "dash"),
                    marker=dict(
                        size=[10, 8],
                        symbol=["triangle-up" if trade["direction"] == "bullish" else "triangle-down", "x"],
                        color=[trade_color, "#ffffff"],
                    ),
                    text=[hover_text, hover_text],
                    hoverinfo="text",
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

            # Draw Stop Loss and Take Profit levels
            fig.add_shape(
                type="line",
                x0=trade["entry_time"],
                x1=trade["exit_time"],
                y0=trade["stop_loss"],
                y1=trade["stop_loss"],
                line=dict(color="rgba(255, 23, 68, 0.45)", width=1, dash="dot"),
                row=1,
                col=1,
            )
            fig.add_shape(
                type="line",
                x0=trade["entry_time"],
                x1=trade["exit_time"],
                y0=trade["take_profit"],
                y1=trade["take_profit"],
                line=dict(color="rgba(0, 230, 118, 0.45)", width=1, dash="dot"),
                row=1,
                col=1,
            )

    # 10. Lower Subplot: ADX Indicator & Chop/Trend Regime Zones
    if not m15_adx.empty and "ADX" in m15_adx:
        fig.add_trace(
            go.Scatter(
                x=m15_adx.index,
                y=m15_adx["ADX"],
                line=dict(color="#00e5ff", width=1.5),
                name="M15 ADX(14)",
            ),
            row=2,
            col=1,
        )

        # Threshold guide lines
        fig.add_hline(
            y=25.0,
            line=dict(color="#00e676", width=1, dash="dash"),
            annotation_text="Trend (25)",
            annotation_position="top right",
            row=2,
            col=1,
        )
        fig.add_hline(
            y=20.0,
            line=dict(color="#ff5252", width=1, dash="dash"),
            annotation_text="Chop (<20)",
            annotation_position="bottom right",
            row=2,
            col=1,
        )

    # Layout Aesthetics
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#12141a",
        plot_bgcolor="#161922",
        title=dict(
            text=f"<b>{symbol} SMC Zone & Fakeout Debugger</b> ({start_date} → {end_date})",
            font=dict(size=18, color="#e0e6ed"),
            x=0.03,
            y=0.98,
        ),
        xaxis=dict(
            rangeslider=dict(visible=False),
            gridcolor="#222836",
            linecolor="#333b4d",
        ),
        yaxis=dict(
            title="Price",
            gridcolor="#222836",
            linecolor="#333b4d",
        ),
        xaxis2=dict(
            gridcolor="#222836",
            linecolor="#333b4d",
        ),
        yaxis2=dict(
            title="ADX",
            gridcolor="#222836",
            linecolor="#333b4d",
            range=[0, 60],
        ),
        height=850,
        margin=dict(l=60, r=40, t=70, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1.0,
            font=dict(color="#a0aec0", size=11),
        ),
        hovermode="closest",
    )

    # Save HTML output
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    fig.write_html(output_html, include_plotlyjs="cdn")
    print(f"\nInteractive visualization exported to:\n  -> {output_html}")
    return output_html


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plotly SMC Visual Debugger")
    parser.add_argument("--symbol", default="XAUUSD", help="Trading symbol")
    parser.add_argument("--start", default="2026-03-02", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2026-03-12", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--trades",
        default="reports/pristine_holdout_spring2026_XAUUSD_trades.csv",
        help="Path to trades CSV",
    )
    parser.add_argument(
        "--output",
        default="reports/visualizations/xauusd_spring2026_chop_debug.html",
        help="Output HTML path",
    )
    args = parser.parse_args()

    create_zone_visualization(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        trades_csv=args.trades,
        output_html=args.output,
    )
