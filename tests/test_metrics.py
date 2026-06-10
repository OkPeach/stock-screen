"""metrics.py: source-aware extraction, labelling, history, sector-aware scoring."""
from pipeline import metrics


class TestExtract:
    def test_finnhub_percent_kept_fmp_fraction_scaled(self):
        # Same conceptual value from each provider must normalize identically.
        fh = metrics.extract({"netProfitMarginTTM": 25.0}, None)
        fmp = metrics.extract(None, {"netProfitMarginTTM": 0.25})
        assert fh["net_margin"] == 25.0
        assert fmp["net_margin"] == 25.0

    def test_finnhub_takes_precedence_over_fmp(self):
        out = metrics.extract({"peTTM": 30}, {"peRatioTTM": 99})
        assert out["pe"] == 30

    def test_debt_to_equity_percent_form_rescaled(self):
        assert metrics.extract({"totalDebt/totalEquityQuarterly": 150}, None)["debt_to_equity"] == 1.5
        assert metrics.extract({"totalDebt/totalEquityQuarterly": 1.5}, None)["debt_to_equity"] == 1.5

    def test_error_dicts_yield_nothing(self):
        assert metrics.extract({"error": "403"}, {"error": "403"}) == {}


class TestLabel:
    PE = metrics.BY_KEY["pe"]            # valuation: cheap/expensive
    ROE = metrics.BY_KEY["roe"]          # higher better: weak/strong
    DE = metrics.BY_KEY["debt_to_equity"]  # lower better: lean/heavy

    def test_valuation_vocabulary(self):
        assert metrics.label(self.PE, 10, 20) == "cheap"
        assert metrics.label(self.PE, 30, 20) == "expensive"
        assert metrics.label(self.PE, 20.5, 20) == "in line"
        assert metrics.label(self.PE, -5, 20) == "negative"

    def test_quality_vocabulary(self):
        assert metrics.label(self.ROE, 40, 20) == "strong"
        assert metrics.label(self.ROE, 10, 20) == "weak"

    def test_debt_vocabulary(self):
        assert metrics.label(self.DE, 0.2, 1.0) == "lean"
        assert metrics.label(self.DE, 2.0, 1.0) == "heavy"

    def test_no_benchmark_means_no_label(self):
        assert metrics.label(self.PE, 10, None) is None
        assert metrics.label(self.PE, 10, 0) is None


class TestHistory:
    def test_series_mapped_and_trimmed(self):
        series = {"quarterly": {"pe": [{"period": f"2024-0{q}-30", "v": 20 + q} for q in range(1, 5)]}}
        out = metrics.history_from_series(series, max_points=3)
        assert out["pe"] == [["2024-02-30", 22], ["2024-03-30", 23], ["2024-04-30", 24]]

    def test_bad_points_skipped(self):
        series = {"quarterly": {"pe": [{"period": "2024-03-30", "v": None}, {"v": 5}, {"period": "2024-06-30", "v": 21}]}}
        assert metrics.history_from_series(series)["pe"] == [["2024-06-30", 21]]

    def test_missing_series_is_empty(self):
        assert metrics.history_from_series(None) == {}
        assert metrics.history_from_series({}) == {}


def _fund(key, tone, word="x", bench=1.0, src="peers"):
    return {"key": key, "label": metrics.BY_KEY[key].label, "tone": tone, "word": word,
            "sector_benchmark": bench, "benchmark_source": src}


class TestScoreFromLabels:
    def test_banks_exclude_balance_sheet_ratios(self):
        assert "debt_to_equity" not in metrics.relevant_metrics("Banking")
        assert "current_ratio" not in metrics.relevant_metrics("Financial Services")
        assert "debt_to_equity" in metrics.relevant_metrics("Technology")

    def test_score_is_mean_of_tones(self):
        funds = [_fund("pe", "bad"), _fund("roe", "good"), _fund("net_margin", "good")]
        res = metrics.score_from_labels(funds, "Technology")
        assert res["score"] == round((1 + 1 - 1) / 3, 3)

    def test_irrelevant_metrics_ignored_for_sector(self):
        # D/E is 'good' but must not lift a bank's score.
        funds = [_fund("pe", "bad"), _fund("roe", "bad"), _fund("net_margin", "bad"),
                 _fund("debt_to_equity", "good")]
        res = metrics.score_from_labels(funds, "Banking")
        assert res["score"] == -1.0

    def test_too_few_benchmarked_metrics_returns_none(self):
        funds = [_fund("pe", "bad"), _fund("roe", "good", bench=None)]
        assert metrics.score_from_labels(funds, "Technology") is None
