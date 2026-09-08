from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime

class TradeBase(BaseModel):
    symbol: str
    direction: Literal['long', 'short']
    entry_price: float = Field(alias='entryPrice')
    exit_price: Optional[float] = Field(None, alias='exitPrice')
    sl: float
    tp: float
    r_multiple: Optional[float] = Field(None, alias='rMultiple')
    outcome: Optional[Literal['win', 'loss', 'breakeven']] = None
    setup_type: str = Field(alias='setupType')
    session: Optional[str] = 'london'
    opened_at: Optional[datetime] = Field(None, alias='openedAt')
    closed_at: Optional[datetime] = Field(None, alias='closedAt')
    source: Optional[str] = 'paper'

    # 1. Context / Bias
    htf_bias: Optional[str] = Field(None, alias='htfBias')
    htf_reason: Optional[str] = Field(None, alias='htfReason')
    bias_correct: Optional[str] = Field(None, alias='biasCorrect')

    # 2. Setup
    setup_timeframe: Optional[str] = Field('M15', alias='setupTimeframe')
    confluence: Optional[str] = Field(None, alias='confluence')
    screenshot_url: Optional[str] = Field(None, alias='screenshotUrl')

    # 3. Execution
    entry_timeframe: Optional[str] = Field('M1', alias='entryTimeframe')
    entry_trigger: Optional[str] = Field(None, alias='entryTrigger')
    sl_logic: Optional[str] = Field(None, alias='slLogic')
    planned_rr: Optional[float] = Field(None, alias='plannedRr')
    risk_pct: Optional[float] = Field(1.0, alias='riskPct')

    # 4. Outcome & Excursion
    points_captured: Optional[float] = Field(None, alias='pointsCaptured')
    mae: Optional[float] = Field(None, alias='mae')
    mfe: Optional[float] = Field(None, alias='mfe')

    # 5. Process & Psychology
    rule_adherence: Optional[str] = Field(None, alias='ruleAdherence')
    emotional_state: Optional[str] = Field(None, alias='emotionalState')
    external_factor: Optional[str] = Field(None, alias='externalFactor')

    # 6. Post-trade review
    textbook_comparison: Optional[str] = Field(None, alias='textbookComparison')
    mistake_type: Optional[str] = Field(None, alias='mistakeType')
    review_notes: Optional[str] = Field(None, alias='reviewNotes')

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

class Trade(TradeBase):
    id: str

class TradeCreate(TradeBase):
    id: Optional[str] = None

class TradeUpdate(BaseModel):
    symbol: Optional[str] = None
    direction: Optional[Literal['long', 'short']] = None
    entry_price: Optional[float] = Field(None, alias='entryPrice')
    exit_price: Optional[float] = Field(None, alias='exitPrice')
    sl: Optional[float] = None
    tp: Optional[float] = None
    r_multiple: Optional[float] = Field(None, alias='rMultiple')
    outcome: Optional[Literal['win', 'loss', 'breakeven']] = None
    setup_type: Optional[str] = Field(None, alias='setupType')
    session: Optional[Literal['asian', 'london', 'ny']] = None
    opened_at: Optional[datetime] = Field(None, alias='openedAt')
    closed_at: Optional[datetime] = Field(None, alias='closedAt')
    source: Optional[str] = None

    htf_bias: Optional[Literal['bullish', 'bearish', 'range']] = Field(None, alias='htfBias')
    htf_reason: Optional[str] = Field(None, alias='htfReason')
    bias_correct: Optional[Literal['yes', 'no', 'partial']] = Field(None, alias='biasCorrect')

    setup_timeframe: Optional[str] = Field(None, alias='setupTimeframe')
    confluence: Optional[str] = Field(None, alias='confluence')
    screenshot_url: Optional[str] = Field(None, alias='screenshotUrl')

    entry_timeframe: Optional[str] = Field(None, alias='entryTimeframe')
    entry_trigger: Optional[str] = Field(None, alias='entryTrigger')
    sl_logic: Optional[str] = Field(None, alias='slLogic')
    planned_rr: Optional[float] = Field(None, alias='plannedRr')
    risk_pct: Optional[float] = Field(None, alias='riskPct')

    points_captured: Optional[float] = Field(None, alias='pointsCaptured')
    mae: Optional[float] = Field(None, alias='mae')
    mfe: Optional[float] = Field(None, alias='mfe')

    rule_adherence: Optional[str] = Field(None, alias='ruleAdherence')
    emotional_state: Optional[str] = Field(None, alias='emotionalState')
    external_factor: Optional[str] = Field(None, alias='externalFactor')

    textbook_comparison: Optional[str] = Field(None, alias='textbookComparison')
    mistake_type: Optional[str] = Field(None, alias='mistakeType')
    review_notes: Optional[str] = Field(None, alias='reviewNotes')

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

