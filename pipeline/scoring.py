"""Combine check scores -> verdict + reasons. (Phase 2)

composite = (w_fund*fund + w_tech*tech + w_sent*sent) / sum(weights of
            dimensions that actually returned data)

Re-normalizing by available weight means a missing dimension (e.g. premium
sentiment on a free plan) doesn't silently drag every verdict toward zero.

verdict = WATCH-BUY | NEUTRAL | WATCH-SELL  (bands from config.yaml)
The dashboard shows the verdict *plus* the contributing reasons — never a bare
number (plan.md §7).
"""
from __future__ import annotations

VERDICT_BUY = "WATCH-BUY"
VERDICT_SELL = "WATCH-SELL"
VERDICT_NEUTRAL = "NEUTRAL"


def _available(check_result: dict) -> bool:
    """A dimension counts toward the composite only if it produced real signal."""
    reasons = check_result.get("reasons", [])
    if not reasons:
        return False
    first = reasons[0].lower()
    return not ("unavailable" in first or "no usable" in first or "no data" in first)


def score_ticker(
    fundamentals: dict,
    technicals: dict,
    sentiment: dict,
    weights: dict,
    bands: dict,
) -> dict:
    """Combine the three scored dimensions into a composite + verdict + reasons."""
    dims = {
        "fundamentals": (fundamentals, float(weights.get("fundamentals", 0.0))),
        "technicals": (technicals, float(weights.get("technicals", 0.0))),
        "sentiment": (sentiment, float(weights.get("sentiment", 0.0))),
    }

    weighted_sum = 0.0
    used_weight = 0.0
    reasons: list[str] = []
    flags: list[str] = []
    for name, (result, weight) in dims.items():
        reasons.extend(f"[{name}] {r}" for r in result.get("reasons", []))
        flags.extend(result.get("flags", []))
        if _available(result) and weight > 0:
            weighted_sum += weight * float(result.get("score", 0.0))
            used_weight += weight

    composite = weighted_sum / used_weight if used_weight > 0 else 0.0
    composite = max(-1.0, min(1.0, composite))

    buy_band = float(bands.get("watch_buy", 0.25))
    sell_band = float(bands.get("watch_sell", -0.25))
    if composite >= buy_band:
        verdict = VERDICT_BUY
    elif composite <= sell_band:
        verdict = VERDICT_SELL
    else:
        verdict = VERDICT_NEUTRAL

    return {
        "composite": round(composite, 3),
        "verdict": verdict,
        "coverage": round(used_weight, 3),
        "reasons": reasons,
        "flags": sorted(set(flags)),
        "scores": {
            "fundamentals": fundamentals.get("score", 0.0),
            "technicals": technicals.get("score", 0.0),
            "sentiment": sentiment.get("score", 0.0),
        },
    }
