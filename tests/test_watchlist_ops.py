"""watchlist.py (config editing) and issue_ops.py (issue-form parsing)."""
import pytest

from pipeline import watchlist, issue_ops

CONFIG = """\
# config.yaml — no API keys here.
watchlist:
  - AAPL
  - MSFT
  - TSLA

# weights below
weights:
  fundamentals: 0.4
"""


@pytest.fixture
def cfg_file(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(CONFIG, encoding="utf-8")
    return p


class TestWatchlist:
    def test_read(self, cfg_file):
        assert watchlist.read_watchlist(cfg_file) == ["AAPL", "MSFT", "TSLA"]

    def test_add_uppercases_and_appends(self, cfg_file):
        changed, wl = watchlist.add_ticker("nflx", cfg_file)
        assert changed and wl[-1] == "NFLX"

    def test_add_duplicate_is_noop(self, cfg_file):
        changed, wl = watchlist.add_ticker("AAPL", cfg_file)
        assert not changed and wl.count("AAPL") == 1

    def test_remove(self, cfg_file):
        changed, wl = watchlist.remove_ticker("TSLA", cfg_file)
        assert changed and "TSLA" not in wl

    def test_remove_absent_is_noop(self, cfg_file):
        changed, _ = watchlist.remove_ticker("ZZZZ", cfg_file)
        assert not changed

    def test_comments_and_other_keys_preserved(self, cfg_file):
        watchlist.add_ticker("NFLX", cfg_file)
        watchlist.remove_ticker("MSFT", cfg_file)
        text = cfg_file.read_text()
        assert "# config.yaml — no API keys here." in text
        assert "# weights below" in text
        assert "fundamentals: 0.4" in text


class TestIssueOps:
    def test_extract_add(self):
        body = "### Action\n\nAdd\n\n### Ticker(s)\n\nNFLX, brk-b 123bad"
        action, valid, rejected = issue_ops.extract(body)
        assert action == "add"
        assert valid == ["NFLX", "BRK-B"]
        assert rejected == ["123BAD"]

    def test_extract_remove(self):
        action, valid, _ = issue_ops.extract("### Action\n\nRemove\n\n### Ticker(s)\n\nTSLA")
        assert action == "remove" and valid == ["TSLA"]

    def test_no_response_placeholder_ignored(self):
        action, valid, rejected = issue_ops.extract("### Action\n\nAdd\n\n### Ticker(s)\n\n_no response_")
        assert valid == [] and rejected == []

    def test_dedupe_preserves_order(self):
        _, valid, _ = issue_ops.extract("### Action\n\nAdd\n\n### Ticker(s)\n\nMSFT aapl MSFT")
        assert valid == ["MSFT", "AAPL"]
