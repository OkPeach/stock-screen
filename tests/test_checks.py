"""Checks: technicals, sentiment, and the absolute-threshold fundamentals fallback."""
import math

from pipeline.checks import technicals, sentiment, fundamentals

TECH_CFG = {"sma_fast": 50, "sma_slow": 200, "rsi_oversold": 30, "rsi_overbought": 70}


def _closes(n=260, slope=0.4, base=80.0):
    return [base + i * slope + 1.5 * math.sin(i / 9) for i in range(n)]


class TestTechnicals:
    def test_uptrend_scores_positive(self):
        res = technicals.check({"c": _closes(slope=0.4), "s": "ok"}, TECH_CFG)
        assert res["metrics"]["sma_fast"] > res["metrics"]["sma_slow"]
        assert any("uptrend" in r for r in res["reasons"])
        assert -1.0 <= res["score"] <= 1.0

    def test_downtrend_scores_negative(self):
        res = technicals.check({"c": _closes(slope=-0.4, base=300.0), "s": "ok"}, TECH_CFG)
        assert any("downtrend" in r for r in res["reasons"])
        assert res["score"] < 0

    def test_short_history_is_neutral_not_crash(self):
        res = technicals.check({"c": _closes(50), "s": "ok"}, TECH_CFG)
        assert res["score"] == 0.0
        assert "candles" in res["reasons"][0]

    def test_error_input_is_neutral(self):
        res = technicals.check({"error": "HTTP 403"}, TECH_CFG)
        assert res["score"] == 0.0
        assert "unavailable" in res["reasons"][0]

    def test_rsi_within_bounds(self):
        res = technicals.check({"c": _closes(), "s": "ok"}, TECH_CFG)
        assert 0 <= res["metrics"]["rsi"] <= 100


class TestSentiment:
    CFG = {"negative_spike": -0.2}

    def test_finnhub_premium_score_preferred(self):
        res = sentiment.check({"companyNewsScore": 0.8}, [{"headline": "irrelevant"}], self.CFG)
        assert res["metrics"]["source"] == "finnhub_news_sentiment"
        assert res["score"] == 0.6  # (0.8 - 0.5) * 2

    def test_vader_fallback_positive_headlines(self):
        news = [{"headline": "Company beats earnings and raises guidance"},
                {"headline": "Analysts upgrade after record quarter"}]
        res = sentiment.check({"error": "403"}, news, self.CFG)
        assert res["metrics"]["source"] == "vader_headlines"
        assert res["score"] > 0

    def test_vader_negative_spike_flag(self):
        news = [{"headline": "Company files for bankruptcy after fraud probe"},
                {"headline": "Shares plunge as lawsuit and recall widen losses"}]
        res = sentiment.check({"error": "403"}, news, self.CFG)
        assert res["score"] < 0
        assert "negative_sentiment_spike" in res["flags"]

    def test_no_headlines_is_neutral(self):
        res = sentiment.check({"error": "403"}, [], self.CFG)
        assert res["score"] == 0.0
        assert res["metrics"]["source"] == "none"


class TestFundamentalsAbsoluteFallback:
    CFG = {"pe_good": 25, "pe_flag": 40, "rev_growth_yoy": 0.05,
           "debt_to_equity_max": 1.5, "require_positive_fcf": True}

    def test_all_good_clamps_to_one(self):
        fin = {"peTTM": 18, "revenueGrowthTTMYoy": 12.0,
               "totalDebt/totalEquityQuarterly": 0.4, "freeCashFlowTTM": 5000}
        res = fundamentals.check(fin, self.CFG)
        assert res["score"] == 1.0

    def test_rich_pe_flags(self):
        res = fundamentals.check({"peTTM": 60}, self.CFG)
        assert "high_pe" in res["flags"]
        assert res["score"] < 0

    def test_percent_vs_fraction_growth_normalized(self):
        # 12.0 (percent form) and 0.12 (fraction form) must score identically.
        a = fundamentals.check({"revenueGrowthTTMYoy": 12.0}, self.CFG)
        b = fundamentals.check({"revenueGrowthTTMYoy": 0.12}, self.CFG)
        assert a["score"] == b["score"] > 0

    def test_no_data_is_neutral(self):
        res = fundamentals.check({"error": "403"}, self.CFG)
        assert res["score"] == 0.0
