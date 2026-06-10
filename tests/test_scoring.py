"""scoring.py: coverage renormalization, verdict bands, clamping."""
from pipeline import scoring

WEIGHTS = {"fundamentals": 0.4, "technicals": 0.35, "sentiment": 0.25}
BANDS = {"watch_buy": 0.25, "watch_sell": -0.25}


def _check(score, reason):
    return {"score": score, "reasons": [reason], "flags": []}


def test_unavailable_dimension_renormalizes_not_drags():
    fund = _check(1.0, "P/E cheap vs peers")
    tech = _check(0.0, "technicals: unavailable (HTTP 403)")
    sent = _check(0.5, "Headline sentiment +0.50 over 10 stories")
    v = scoring.score_ticker(fund, tech, sent, WEIGHTS, BANDS)
    assert v["coverage"] == 0.65  # 0.4 + 0.25
    assert v["composite"] == round((0.4 * 1.0 + 0.25 * 0.5) / 0.65, 3)
    assert v["verdict"] == "WATCH-BUY"


def test_all_unavailable_is_neutral():
    dead = _check(0.0, "fundamentals: no usable metrics on this plan")
    v = scoring.score_ticker(dead, _check(0, "technicals: unavailable (x)"),
                             _check(0, "sentiment: no data"), WEIGHTS, BANDS)
    assert v["coverage"] == 0.0
    assert v["verdict"] == "NEUTRAL"


def test_verdict_bands():
    full = lambda s: _check(s, "signal")
    buy = scoring.score_ticker(full(1), full(1), full(1), WEIGHTS, BANDS)
    sell = scoring.score_ticker(full(-1), full(-1), full(-1), WEIGHTS, BANDS)
    flat = scoring.score_ticker(full(0.1), full(0.1), full(0.1), WEIGHTS, BANDS)
    assert buy["verdict"] == "WATCH-BUY"
    assert sell["verdict"] == "WATCH-SELL"
    assert flat["verdict"] == "NEUTRAL"


def test_composite_clamped_and_flags_merged():
    fund = {"score": 5.0, "reasons": ["x"], "flags": ["high_pe"]}
    tech = {"score": 5.0, "reasons": ["y"], "flags": ["rsi_overbought"]}
    v = scoring.score_ticker(fund, tech, _check(0, "sentiment: no data"), WEIGHTS, BANDS)
    assert v["composite"] <= 1.0
    assert set(v["flags"]) == {"high_pe", "rsi_overbought"}


def test_reasons_carry_dimension_prefix():
    v = scoring.score_ticker(_check(0.5, "P/E cheap"), _check(0.2, "uptrend"),
                             _check(0.1, "calm news"), WEIGHTS, BANDS)
    assert "[fundamentals] P/E cheap" in v["reasons"]
    assert "[technicals] uptrend" in v["reasons"]
