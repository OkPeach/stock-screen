"""Fundamentals check -> score in -1..+1 plus reasons/flags. (Phase 2)

Input is the Finnhub basic-financials `metric` dict. Field names vary by plan,
so each value is looked up across a list of candidate keys and missing data
degrades gracefully (neutral contribution + a reason) rather than failing.
"""
from __future__ import annotations


def _first(metrics: dict, *keys: str):
    for k in keys:
        v = metrics.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def check(financials: dict, cfg: dict) -> dict:
    """Return {score, reasons, flags, metrics} for the fundamentals dimension."""
    reasons: list[str] = []
    flags: list[str] = []

    if not isinstance(financials, dict) or "error" in financials or not financials:
        msg = financials.get("error") if isinstance(financials, dict) else "no data"
        return {"score": 0.0, "reasons": [f"fundamentals: unavailable ({msg})"], "flags": [], "metrics": {}}

    pe = _first(financials, "peTTM", "peBasicExclExtraTTM", "peNormalizedAnnual")
    rev_growth = _first(financials, "revenueGrowthTTMYoy", "revenueGrowthQuarterlyYoy", "revenueGrowth5Y")
    debt_to_equity = _first(
        financials, "totalDebt/totalEquityQuarterly", "totalDebt/totalEquityAnnual",
        "longTermDebt/equityQuarterly", "longTermDebt/equityAnnual",
    )
    fcf = _first(financials, "freeCashFlowTTM", "freeCashFlowAnnual", "freeCashFlowPerShareTTM")

    score = 0.0
    seen = 0

    pe_good = float(cfg.get("pe_good", 25))
    pe_flag = float(cfg.get("pe_flag", 40))
    if pe is not None:
        seen += 1
        if pe <= 0:
            score -= 0.2
            reasons.append(f"P/E {pe:.1f} (negative earnings)")
            flags.append("negative_earnings")
        elif pe < pe_good:
            score += 0.4
            reasons.append(f"P/E {pe:.1f} < {pe_good:.0f} (attractive)")
        elif pe > pe_flag:
            score -= 0.4
            reasons.append(f"P/E {pe:.1f} > {pe_flag:.0f} (rich)")
            flags.append("high_pe")
        else:
            reasons.append(f"P/E {pe:.1f} (fair)")

    thr_growth = float(cfg.get("rev_growth_yoy", 0.05))
    if rev_growth is not None:
        seen += 1
        # Finnhub may express growth as a fraction or a percent; normalize.
        g = rev_growth / 100 if abs(rev_growth) > 1.5 else rev_growth
        if g > thr_growth:
            score += 0.3
            reasons.append(f"Revenue growth {g*100:.1f}% YoY > {thr_growth*100:.0f}%")
        else:
            score -= 0.1
            reasons.append(f"Revenue growth {g*100:.1f}% YoY (soft)")

    de_max = float(cfg.get("debt_to_equity_max", 1.5))
    if debt_to_equity is not None:
        seen += 1
        de = debt_to_equity / 100 if debt_to_equity > 5 else debt_to_equity
        if de < de_max:
            score += 0.2
            reasons.append(f"Debt/Equity {de:.2f} < {de_max:.1f}")
        else:
            score -= 0.2
            reasons.append(f"Debt/Equity {de:.2f} > {de_max:.1f} (leveraged)")
            flags.append("high_leverage")

    if cfg.get("require_positive_fcf", True) and fcf is not None:
        seen += 1
        if fcf > 0:
            score += 0.2
            reasons.append("Positive free cash flow")
        else:
            score -= 0.2
            reasons.append("Negative free cash flow")
            flags.append("negative_fcf")

    if seen == 0:
        return {"score": 0.0, "reasons": ["fundamentals: no usable metrics on this plan"], "flags": [], "metrics": {}}

    score = max(-1.0, min(1.0, score))
    return {
        "score": round(score, 3),
        "reasons": reasons,
        "flags": flags,
        "metrics": {"pe": pe, "rev_growth": rev_growth, "debt_to_equity": debt_to_equity, "fcf": fcf},
    }
