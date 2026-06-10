"""Data clients: Yahoo payload parsing (offline) and the peer-benchmark cache."""
import pytest

from pipeline.data import yahoo_client
from pipeline import peers


def _payload(ts, closes, error=None):
    return {"chart": {"error": error, "result": [{
        "timestamp": ts,
        "indicators": {"quote": [{"close": closes,
                                  "open": closes, "high": closes, "low": closes,
                                  "volume": [1] * len(closes)}]},
    }] if error is None else []}}


class TestYahooParse:
    def test_basic_parse_oldest_to_newest(self):
        day = 86400
        out = yahoo_client._parse(_payload([day, 2 * day, 3 * day], [1.0, 2.0, 3.0]), "X", days=400)
        assert out["s"] == "ok"
        assert out["c"] == [1.0, 2.0, 3.0]
        assert out["t"][0] < out["t"][-1]

    def test_null_closes_skipped(self):
        day = 86400
        out = yahoo_client._parse(_payload([day, 2 * day, 3 * day], [1.0, None, 3.0]), "X", days=400)
        assert out["c"] == [1.0, 3.0]

    def test_days_trims_from_the_end(self):
        day = 86400
        out = yahoo_client._parse(_payload([i * day for i in range(1, 6)], [1, 2, 3, 4, 5]), "X", days=2)
        assert out["c"] == [4.0, 5.0]

    def test_chart_error_raises(self):
        with pytest.raises(yahoo_client.YahooError):
            yahoo_client._parse(_payload([], [], error={"code": "Not Found"}), "X", days=10)

    def test_empty_result_raises(self):
        with pytest.raises(yahoo_client.YahooError):
            yahoo_client._parse({"chart": {"result": []}}, "X", days=10)


class TestPeerBenchmarks:
    @pytest.fixture
    def wired(self, monkeypatch, tmp_path):
        self.peer_calls = {"n": 0}

        def get_peers(s, **k):
            self.peer_calls["n"] += 1
            return ["P1", "P2"]

        monkeypatch.setattr(peers.fh, "get_peers", get_peers)
        monkeypatch.setattr(peers.fh, "get_basic_financials",
                            lambda s, **k: {"peTTM": {"P1": 10, "P2": 20}[s]})
        monkeypatch.setattr(peers, "CACHE_PATH", tmp_path / "bm.json")
        monkeypatch.setattr("time.sleep", lambda *a: None)

    def test_median_of_peers(self, wired):
        bm = peers.build_benchmarks(["AAPL"])
        assert bm["AAPL"]["values"]["pe"] == 15.0   # median of 10, 20
        assert bm["AAPL"]["peers"] == 2

    def test_cache_prevents_refetch(self, wired):
        peers.build_benchmarks(["AAPL"])
        first = self.peer_calls["n"]
        bm = peers.build_benchmarks(["AAPL"])     # second run: served from cache
        assert self.peer_calls["n"] == first
        assert bm["AAPL"]["values"]["pe"] == 15.0
