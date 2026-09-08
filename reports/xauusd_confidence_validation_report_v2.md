# XAUUSD Out-of-Sample Confidence & Measurement Report (v2 - Fixed Scan & Extended Data)

**Generated**: 2026-09-08

## Executive Summary
This report presents an extended, multi-year out-of-sample backtest validation for **XAUUSD (Gold)**.
A thorough audit of prior test scripts revealed that **August 2026** (and Summer 2026 generally) was heavily contaminated by repeated use in parameter tuning, regime benchmarking, and control comparisons. Removing August 2026 from the prior 7-month dataset drops its expectancy to **-0.04R**.
To eliminate data leakage and build true statistical confidence, this evaluation expanded coverage across **17 TRULY UNTOUCHED calendar months** (July 2024 through November 2025) using historical bars fetched directly from MetaTrader 5.

## 1. Audit of Previously Tested XAUUSD Date Ranges (Step 1)

| Date Range | Source Script / Document | Category | Contamination Status |
|---|---|---|---|
| 2025-12-01 to 2026-02-27 | `run_fresh_walkforward_step7.py / step11 / step12` | Tuning Data | **CONTAMINATED** |
| 2026-01-05 to 2026-03-31 | `run_walkforward_step13.py` | Tuning Data | **CONTAMINATED** |
| 2026-03-02 to 2026-05-29 | `run_pristine_holdout_tests.py / explore_regime_adx.py` | Pristine Holdout | **CONTAMINATED** |
| 2026-06-01 to 2026-06-30 | `run_walkforward_step16_final.py` | Out-of-Sample | **CONTAMINATED** |
| 2026-06-08 to 2026-09-02 | `run_pristine_holdout_tests.py` | Holdout Control | **CONTAMINATED** |
| 2026-08-06 to 2026-09-02 | `test_regime_candidates.py / verify_regime_distribution.py` | Regime Benchmark | **HIGHLY CONTAMINATED** |
| 2026-03-01 to 2026-09-02 | `run_xauusd_journal_backtest.py` | Journal Sync | **CONTAMINATED** |

> [!CAUTION]
> **All data between December 1, 2025 and September 2, 2026 has been touched or tuned against in prior steps.**
> August 2026 was explicitly used in `explore_regime_adx.py` and `test_regime_candidates.py` as the benchmark for strong trends, rendering it invalid for out-of-sample testing.

## 2. Available MT5 Data & Truly Untouched Months (Step 2)

- **Broker History Start**: 2024-01-02
- **Evaluated Range**: July 2024 to November 2025 (17 consecutive untouched months)
- **Total Untouched Months**: **17 months**

## 3. Per-Month Out-of-Sample Performance Table (Step 3 & 4)

| Month | Trades | Win Rate | Net PnL ($) | Expectancy (R) | Profit Factor | Max Drawdown | 10% DD Circuit Breaker Hit |
|---|---|---|---|---|---|---|---|
| July 2024 | 4 | 0.0% | $-400.96 | -1.00R | 0.00 | 4.0% | No |
| August 2024 | 3 | 33.3% | $-65.27 | -0.17R | 0.68 | 2.0% | No |
| September 2024 | 6 | 33.3% | $-131.65 | -0.20R | 0.69 | 2.0% | No |
| October 2024 | 47 | 46.8% | $+268.20 | +0.09R | 1.15 | 9.2% | No |
| November 2024 | 5 | 20.0% | $-267.56 | -0.52R | 0.35 | 3.0% | No |
| December 2024 | 0 | N/A | $0.00 | 0.00R | N/A | 0.0% | No |
| January 2025 | 0 | N/A | $0.00 | 0.00R | N/A | 0.0% | No |
| February 2025 | 23 | 39.1% | $-211.17 | -0.07R | 0.87 | 8.5% | No |
| March 2025 | 21 | 42.9% | $-43.99 | +0.00R | 1.00 | 5.0% | No |
| April 2025 | 16 | 12.5% | $-1,064.29 | -0.69R | 0.20 | 10.6% | **YES (STOP)** |
| May 2025 | 11 | 45.5% | $+81.93 | +0.10R | 1.16 | 3.1% | No |
| June 2025 | 0 | N/A | $0.00 | 0.00R | N/A | 0.0% | No |
| July 2025 | 0 | N/A | $0.00 | 0.00R | N/A | 0.0% | No |
| August 2025 | 0 | N/A | $0.00 | 0.00R | N/A | 0.0% | No |
| September 2025 | 7 | 28.6% | $-222.35 | -0.31R | 0.56 | 4.9% | No |
| October 2025 | 50 | 42.0% | $+79.15 | +0.03R | 1.04 | 9.8% | No |
| November 2025 | 24 | 41.7% | $-26.85 | +0.01R | 1.00 | 5.5% | No |

## 4. Aggregate Performance (All 17 Untouched Months Combined)

- **Total Fresh Trades**: **217**
- **Wins / Losses**: 84 Wins / 133 Losses
- **Overall Win Rate**: **38.7%**
- **Combined Net PnL**: **$-1,664.34**
- **Overall Expectancy**: **-0.07R**
- **Overall Profit Factor**: **0.87**

## 5. Market Regime Breakdown

| Market Regime | Trades | Win Rate | Expectancy (R) | Net PnL ($) |
|---|---|---|---|---|
| Trending | 174 | 36.8% | -0.12R | $-2,167.56 |
| Choppy | 0 | N/A | 0.00R | $0.00 |
| Transitional | 43 | 46.5% | +0.13R | $+503.22 |

## 6. Confluence Tier Breakdown

| Confluence Tier | Trades | Win Rate | Expectancy (R) | Net PnL ($) |
|---|---|---|---|---|
| Tier 70-74 | 117 | 39.3% | -0.07R | $-887.68 |
| Tier 75-79 | 100 | 38.0% | -0.07R | $-776.66 |
| Tier 80+ (Blocked) | 0 | N/A | 0.00R | $0.00 |

## 7. Statistical Confidence & Trade Count Assessment (Step 5)

> [!TIP]
> **STATISTICAL GUARD PASSED**: Total fresh trade count across 17 untouched months is **217 trades** (>= 100 threshold), providing a robust sample size across multiple market regimes without parameter tuning.
