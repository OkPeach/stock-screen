"""Alerts check -> threshold flags (no score). (Phase 2)

These flags don't move the composite score; they're surfaced on the dashboard
and consumed by notify.py in Phase 5. Inputs are the Finnhub quote dict and the
basic-financials metric dict.
"""
from __future__ import annotations


def check(quote: dict, financials: dict, cfg: dict) -> dict:
    """Return {flags, reasons, metrics} of triggered alerts."""
    flags: list[str] = []
    reasons: list[str] = []
    metrics: dict = {}

    if isinstance(quote, dict):
        dp = quote.get("dp")  # daily percent change
        if dp is not None:
            metrics["daily_move_pct"] = dp
            limit = float(cfg.get("daily_move_pct", 5.0))
            if abs(dp) >= limit:
                flags.append("big_daily_move")
                reasons.append(f"Daily move {dp:+.1f}% (>= {limit:.0f}%)")

        price = quote.get("c")
        if price is not None and isinstance(financials, dict) and "error" not in financials:
            hi = financials.get("52WeekHigh")
            lo = financials.get("52WeekLow")
            try:
                if cfg.get("flag_52wk_high", True) and hi and price >= float(hi) * 0.99:
                    flags.append("near_52wk_high")
                    reasons.append(f"Near 52-wk high ({price} vs {hi})")
                if cfg.get("flag_52wk_low", True) and lo and price <= float(lo) * 1.01:
                    flags.append("near_52wk_low")
                    reasons.append(f"Near 52-wk low ({price} vs {lo})")
            except (TypeError, ValueError):
                pass

    return {"flags": flags, "reasons": reasons, "metrics": metrics}
