"""Sentiment check -> score in -1..+1 plus reasons/flags. (free)

Order of preference:
  1. Finnhub /news-sentiment companyNewsScore (only on premium plans).
  2. Local VADER scoring of the free company-news headlines — no API, no cost.
  3. Neutral, if there are no headlines at all.

VADER is general-purpose, so we nudge its lexicon with a few finance terms
("beat", "miss", "downgrade", ...) that carry clear directional meaning in
market headlines.
"""
from __future__ import annotations

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Headline terms VADER doesn't weight well out of the box (scale roughly -4..4).
_FINANCE_LEXICON = {
    "beat": 2.0, "beats": 2.0, "tops": 1.8, "surge": 2.5, "surges": 2.5,
    "soar": 2.8, "soars": 2.8, "rally": 1.8, "upgrade": 2.2, "upgraded": 2.2,
    "outperform": 2.0, "record": 1.5, "raises": 1.5, "jumps": 1.8,
    "miss": -2.0, "misses": -2.0, "plunge": -2.8, "plunges": -2.8,
    "slump": -2.2, "downgrade": -2.2, "downgraded": -2.2, "cut": -1.5,
    "cuts": -1.5, "lawsuit": -1.8, "probe": -1.6, "recall": -1.8,
    "warning": -1.5, "bankruptcy": -3.0, "fraud": -3.0, "selloff": -2.2,
    "tumble": -2.2, "tumbles": -2.2, "underperform": -2.0,
}

_analyzer = SentimentIntensityAnalyzer()
_analyzer.lexicon.update(_FINANCE_LEXICON)


def _from_finnhub(sentiment: dict) -> tuple[float, list[str]] | None:
    if not isinstance(sentiment, dict) or "error" in sentiment:
        return None
    score01 = sentiment.get("companyNewsScore")
    if score01 is None:
        return None
    try:
        s = (float(score01) - 0.5) * 2
    except (TypeError, ValueError):
        return None
    return max(-1.0, min(1.0, s)), [f"News-sentiment score {float(score01):.2f} (Finnhub)"]


def _from_headlines(news: list) -> tuple[float, list[str], dict] | None:
    if not isinstance(news, list) or not news:
        return None
    compounds = []
    for item in news:
        text = " ".join(str(item.get(f, "")) for f in ("headline", "summary")).strip()
        if text:
            compounds.append(_analyzer.polarity_scores(text)["compound"])
    if not compounds:
        return None
    avg = sum(compounds) / len(compounds)
    pos = sum(1 for c in compounds if c > 0.05)
    neg = sum(1 for c in compounds if c < -0.05)
    reason = f"Headline sentiment {avg:+.2f} over {len(compounds)} stories ({pos}+ / {neg}-, VADER)"
    return max(-1.0, min(1.0, avg)), [reason], {"source": "vader_headlines", "stories": len(compounds), "avg": round(avg, 3)}


def check(sentiment: dict, news: list | dict, cfg: dict) -> dict:
    """Return {score, reasons, flags, metrics} for the sentiment dimension."""
    flags: list[str] = []
    neg_spike = float(cfg.get("negative_spike", -0.5))

    primary = _from_finnhub(sentiment)
    if primary is not None:
        score, reasons = primary
        if score < neg_spike:
            flags.append("negative_sentiment_spike")
            reasons.append("Negative sentiment spike")
        return {"score": round(score, 3), "reasons": reasons, "flags": flags,
                "metrics": {"source": "finnhub_news_sentiment"}}

    local = _from_headlines(news if isinstance(news, list) else [])
    if local is not None:
        score, reasons, metrics = local
        if score < neg_spike:
            flags.append("negative_sentiment_spike")
            reasons.append("Negative sentiment spike")
        return {"score": round(score, 3), "reasons": reasons, "flags": flags, "metrics": metrics}

    return {"score": 0.0, "reasons": ["Sentiment: no recent headlines (neutral)"], "flags": [],
            "metrics": {"source": "none"}}
