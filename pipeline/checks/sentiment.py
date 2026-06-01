"""Sentiment check -> score in -1..+1 plus reasons/flags. (Phase 2)

Primary source is Finnhub /news-sentiment (companyNewsScore, 0..1). That
endpoint is premium on current free plans, so when it's missing we fall back to
a light heuristic over recent headlines (volume only) and report low confidence.
"""
from __future__ import annotations


def _from_news_sentiment(sentiment: dict) -> tuple[float, list[str]] | None:
    """Map Finnhub companyNewsScore (0..1) to -1..+1, if present."""
    if not isinstance(sentiment, dict) or "error" in sentiment:
        return None
    score01 = sentiment.get("companyNewsScore")
    if score01 is None:
        return None
    try:
        s = (float(score01) - 0.5) * 2  # 0..1 -> -1..1
    except (TypeError, ValueError):
        return None
    return max(-1.0, min(1.0, s)), [f"News-sentiment score {float(score01):.2f} (Finnhub)"]


def check(sentiment: dict, news: list | dict, cfg: dict) -> dict:
    """Return {score, reasons, flags, metrics} for the sentiment dimension."""
    flags: list[str] = []
    neg_spike = float(cfg.get("negative_spike", -0.5))

    primary = _from_news_sentiment(sentiment)
    if primary is not None:
        score, reasons = primary
        if score < neg_spike:
            flags.append("negative_sentiment_spike")
            reasons.append("Negative sentiment spike")
        return {"score": round(score, 3), "reasons": reasons, "flags": flags,
                "metrics": {"source": "finnhub_news_sentiment"}}

    # Fallback: we only have headline volume, no polarity -> stay neutral.
    count = len(news) if isinstance(news, list) else 0
    reason = (
        f"Sentiment unavailable (premium endpoint); {count} recent headlines, "
        "treated as neutral"
    )
    return {"score": 0.0, "reasons": [reason], "flags": [], "metrics": {"source": "fallback", "headlines": count}}
