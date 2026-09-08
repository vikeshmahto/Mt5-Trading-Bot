# XAUUSD Expanded Out-of-Sample Confidence & Measurement Report

**Generated**: 2026-09-08 12:21 UTC
**Instrument**: XAUUSD Gold (All Untouched Fresh Months Combined)

## 1. Previously Tested XAUUSD Date Ranges

| Date Range | Source Script | Category | Notes |
|---|---|---|---|
| 2025-12-01 to 2026-02-27 | run_fresh_walkforward_step7.py | Tuning Data | Initial parameter optimization |
| 2026-01-05 to 2026-03-31 | run_walkforward_step13.py | Tuning Data | Q1 Walk-forward tuning |
| 2026-03-02 to 2026-05-29 | run_pristine_holdout_tests.py | Pristine Holdout | Spring 2026 holdout dataset |
| 2026-06-01 to 2026-06-30 | run_walkforward_step16_final.py | Out-of-Sample | June 2026 validation run |
| 2026-03-01 to 2026-09-02 | run_xauusd_journal_backtest.py | Journal Sync | Full historical journal sync |

## 2. Per-Month Out-of-Sample Performance Table

| Month | Trades | Win Rate | Net PnL | Expectancy (R) | Profit Factor | Max Drawdown | 10% DD Hit |
|---|---|---|---|---|---|---|---|
| August 2025 | 0 | N/A | $0.00 | 0.00R | N/A | 0.0% | No |
| September 2025 | 7 | 28.6% | $-222.35 | -0.31R | 0.56 | 4.9% | No |
| October 2025 | 50 | 42.0% | $+79.15 | +0.03R | 1.04 | 9.8% | No |
| November 2025 | 24 | 41.7% | $-26.85 | +0.01R | 1.00 | 5.5% | No |
| June 2026 | 15 | 40.0% | $+12.52 | -0.01R | 1.02 | 4.5% | No |
| July 2026 | 11 | 27.3% | $-381.09 | -0.34R | 0.53 | 3.9% | No |
| August 2026 | 13 | 61.5% | $+671.82 | +0.51R | 2.28 | 3.0% | No |

## 3. Aggregate Performance Across All Fresh Months Combined

- **Total Fresh Trades Executed**: **120**
- **Wins / Losses**: 50 Wins / 70 Losses
- **Overall Win Rate**: **41.7%**
- **Combined Net PnL**: **$+245.25**
- **Overall Expectancy**: **+0.02R**
- **Profit Factor**: **1.03**
- **Daily-Resampled Sharpe Ratio**: **0.71**

## 4. Market Regime Breakdown

| Regime Type | Trades | Win Rate | Expectancy (R) | Net PnL |
|---|---|---|---|---|
| Trending | 0 | N/A | 0.00R | $0.00 |
| Ranging | 26 | 42.3% | +0.03R | $+65.81 |
| Transitional | 94 | 41.5% | +0.01R | $+179.44 |

## 5. Confluence Tier Breakdown

| Confluence Tier | Trades | Win Rate | Expectancy (R) | Net PnL |
|---|---|---|---|---|
| Tier 70-74 | 52 | 34.6% | -0.16R | $-824.33 |
| Tier 75-79 | 68 | 47.1% | +0.15R | $+1,069.58 |
| Tier 80+ (Blocked) | 0 | N/A | 0.00R | $0.00 |

## 6. Statistical Confidence Guard Assessment

> [!IMPORTANT]
> **Sample Size Validated**: Total fresh trade sample is **120 trades** (exceeds 100 trade threshold). Sample size provides statistical confidence for baseline performance.
