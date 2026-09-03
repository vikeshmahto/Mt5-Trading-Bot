import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

import streamlit as st
import pandas as pd
import plotly.express as px

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.db import get_engine
from core.logger import get_logger

log = get_logger("dashboard")

st.set_page_config(page_title="MT5 SMC Live Dashboard", layout="wide")

# ── Data Fetching ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=5)
def get_dashboard_data():
    engine = get_engine()
    
    # 1. Heartbeat
    try:
        hb_df = pd.read_sql(
            "SELECT * FROM system_status WHERE id = 'live_runner'", 
            engine
        )
        heartbeat = hb_df.iloc[0].to_dict() if not hb_df.empty else None
    except Exception as e:
        log.error(f"Error fetching heartbeat: {e}")
        heartbeat = None
        
    # 2. Last Signal
    try:
        sig_df = pd.read_sql(
            "SELECT * FROM signal_logs WHERE environment = 'paper' ORDER BY timestamp DESC LIMIT 1",
            engine
        )
        last_signal = sig_df.iloc[0].to_dict() if not sig_df.empty else None
    except Exception as e:
        log.error(f"Error fetching last signal: {e}")
        last_signal = None

    # 3. Trades
    try:
        trades_df = pd.read_sql(
            "SELECT * FROM trades WHERE environment = 'paper' ORDER BY entry_time DESC",
            engine
        )
        
        # Merge some signal info into trades for the UI
        if not trades_df.empty:
            signal_ids = tuple(trades_df['signal_id'].astype(str).tolist())
            if len(signal_ids) == 1:
                # pandas read_sql IN clause issues with single tuples sometimes
                q = f"SELECT id as signal_id, confluence_score, signal_type, direction FROM signal_logs WHERE id = '{signal_ids[0]}'"
            else:
                q = f"SELECT id as signal_id, confluence_score, signal_type, direction FROM signal_logs WHERE id IN {signal_ids}"
                
            sig_info = pd.read_sql(q, engine)
            trades_df['signal_id'] = trades_df['signal_id'].astype(str)
            sig_info['signal_id'] = sig_info['signal_id'].astype(str)
            trades_df = pd.merge(trades_df, sig_info, on='signal_id', how='left')
            
            # Ensure timestamps are parsed
            trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
            if 'exit_time' in trades_df.columns:
                trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
            else:
                trades_df['exit_time'] = pd.NaT

            # Sort older to newer for cumulative PnL
            trades_df = trades_df.sort_values('entry_time').reset_index(drop=True)
            trades_df['cumulative_pnl'] = trades_df['pnl_usd'].fillna(0).cumsum()
            trades_df = trades_df.sort_values('entry_time', ascending=False)

    except Exception as e:
        log.error(f"Error fetching trades: {e}")
        trades_df = pd.DataFrame()

    return heartbeat, last_signal, trades_df


def render_dashboard():
    st.title("MT5 SMC Paper Trading Dashboard")
    
    heartbeat, last_signal, trades_df = get_dashboard_data()
    
    # ── 1. Live Status Header ────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Runner Status")
        if heartbeat:
            # check how old it is
            try:
                hb_time = heartbeat['timestamp']
                # SQLAlchemy might return naive datetime or timezone aware depending on driver. Ensure timezone.
                if hb_time.tzinfo is None:
                    hb_time = hb_time.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - hb_time).total_seconds()
                
                if age < 120:
                    st.success(f"🟢 ACTIVE (Last heartbeat: {int(age)}s ago)")
                else:
                    st.error(f"🔴 OFFLINE (Last heartbeat: {int(age)}s ago)")
                
                extra = json.loads(heartbeat.get('extra_info', '{}'))
                st.caption(f"Active Symbols: {extra.get('active_symbols', [])}")
            except Exception as e:
                st.warning(f"Status parsing error: {e}")
        else:
            st.warning("No heartbeat data found.")
            
    with col2:
        st.subheader("Last Signal Checked")
        if last_signal:
            ts = last_signal['timestamp']
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            st.markdown(f"**{ts.strftime('%Y-%m-%d %H:%M:%S UTC')}**")
            st.markdown(f"{last_signal.get('symbol')} {last_signal.get('direction', '').upper()} `{last_signal.get('signal_type')}`")
            if last_signal.get('executed'):
                st.success("Resulted in Trade")
            else:
                st.info("Ignored / No Fill")
        else:
            st.info("No signals generated yet.")
            
    with col3:
        st.subheader("Dashboard Actions")
        if st.button("🔄 Manual Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")
    
    # Empty state handling
    if trades_df.empty:
        st.info("No trades found in the 'paper' environment yet.")
        return

    # ── 2. Win Rate / Expectancy Stats ───────────────────────────────────────
    st.subheader("Performance Metrics")
    
    now = datetime.now(timezone.utc)
    one_week_ago = now - timedelta(days=7)
    
    # Ensure entry_time has timezone
    if trades_df['entry_time'].dt.tz is None:
         trades_df['entry_time'] = trades_df['entry_time'].dt.tz_localize('UTC')
         
    closed_trades = trades_df[trades_df['exit_reason'].notna() & (trades_df['exit_reason'] != '')]
    recent_closed = closed_trades[closed_trades['entry_time'] >= one_week_ago]
    
    def calc_stats(df):
        total = len(df)
        if total == 0:
            return 0, 0, 0.0
        wins = len(df[df['pnl_r'] > 0])
        win_rate = (wins / total) * 100
        expectancy = df['pnl_r'].mean()
        return total, win_rate, expectancy

    at_total, at_wr, at_exp = calc_stats(closed_trades)
    wk_total, wk_wr, wk_exp = calc_stats(recent_closed)
    
    # Calculate Max DD % (Approximation from cumulative PnL)
    # Since we don't have absolute equity historically perfectly tracked without starting balance,
    # we'll calculate peak-to-trough in USD and assume 10k start for % or just show absolute USD DD.
    # Better: use the extra_info balance if available to infer starting balance.
    starting_balance = 10000.0
    if heartbeat:
         extra = json.loads(heartbeat.get('extra_info', '{}'))
         current_balance = extra.get('balance', 10000.0)
         # Approximate starting balance:
         starting_balance = current_balance - closed_trades['pnl_usd'].sum()
    
    temp_df = closed_trades.sort_values('entry_time').copy()
    temp_df['equity'] = starting_balance + temp_df['pnl_usd'].cumsum()
    temp_df['peak'] = temp_df['equity'].cummax()
    temp_df['dd_pct'] = (temp_df['peak'] - temp_df['equity']) / temp_df['peak'] * 100
    max_dd = temp_df['dd_pct'].max() if not temp_df.empty else 0.0

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("All-Time Trades", f"{at_total}", f"Past Week: {wk_total}")
    mc2.metric("All-Time Win Rate", f"{at_wr:.1f}%", f"Past Week: {wk_wr:.1f}%")
    mc3.metric("All-Time Expectancy", f"{at_exp:+.2f}R", f"Past Week: {wk_exp:+.2f}R")
    mc4.metric("Max Drawdown", f"{max_dd:.1f}%", "-10.0% Limit" if max_dd < 10 else "LIMIT EXCEEDED!", delta_color="inverse")
    
    # Success Criteria Progress
    st.markdown("### Success Criteria Check")
    sc1, sc2, sc3 = st.columns(3)
    if at_exp > 0.05:
        sc1.success(f"✅ Expectancy > 0.05R ({at_exp:+.2f}R)")
    else:
        sc1.error(f"❌ Expectancy > 0.05R ({at_exp:+.2f}R)")
        
    if max_dd < 10.0:
        sc2.success(f"✅ Max DD < 10% ({max_dd:.1f}%)")
    else:
        sc2.error(f"❌ Max DD < 10% ({max_dd:.1f}%)")
        
    paper_start = trades_df['entry_time'].min()
    days_running = (now - paper_start).days
    weeks_running = days_running / 7
    if weeks_running >= 4:
        sc3.success(f"✅ Duration >= 4 weeks ({weeks_running:.1f} weeks)")
    else:
        sc3.warning(f"⏳ Duration >= 4 weeks ({weeks_running:.1f} weeks)")

    st.markdown("---")

    # ── 3. Equity Curve Chart ────────────────────────────────────────────────
    st.subheader("Cumulative PnL (USD)")
    
    plot_df = trades_df.sort_values('entry_time').dropna(subset=['cumulative_pnl'])
    if not plot_df.empty:
        fig = px.line(plot_df, x='entry_time', y='cumulative_pnl', markers=True,
                      hover_data=['symbol', 'pnl_usd', 'pnl_r', 'exit_reason'])
        
        # Add a rough 10% drawdown reference line (assuming 10k start, -1000)
        # It's better to show a dynamic line if possible, but a static -10% of starting balance is a good visual guide.
        drawdown_line_usd = -(starting_balance * 0.10)
        fig.add_hline(y=drawdown_line_usd, line_dash="dash", line_color="red", annotation_text="10% Drawdown Limit")
        
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ── 4. Trade List Table ──────────────────────────────────────────────────
    st.subheader("Trade Log")
    
    display_cols = ['entry_time', 'symbol', 'direction', 'signal_type', 'confluence_score', 
                    'entry_price', 'exit_price', 'exit_reason', 'pnl_usd', 'pnl_r']
    
    # Filter only available columns to avoid errors if some are missing
    avail_cols = [c for c in display_cols if c in trades_df.columns]
    df_display = trades_df[avail_cols].copy()
    
    # Sort
    df_display = df_display.sort_values('entry_time', ascending=False)
    
    def color_pnl(val):
        if pd.isna(val):
            return ''
        color = 'green' if val > 0 else 'red' if val < 0 else 'gray'
        return f'color: {color}'

    styled_df = df_display.style.map(color_pnl, subset=['pnl_usd', 'pnl_r'])
    st.dataframe(styled_df, use_container_width=True)

if __name__ == "__main__":
    render_dashboard()
