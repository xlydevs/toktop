import io
import json
import os
import time

from toktop import config, prices


def fake_urlopen(payload):
    def _open(req, timeout=None):
        return io.BytesIO(json.dumps(payload).encode())
    return _open


PAYLOAD = {"data": [
    {"id": "acme/super-model-1.5-contributor", "pricing": {"prompt": "0.0000001", "completion": "0.0000002"}},
    {"id": "acme/super-model-1.5", "pricing": {"prompt": "0.000002", "completion": "0.00001",
                                               "input_cache_read": "0.0000002", "input_cache_write": "0.0000025"}},
    {"id": "acme/super-model-1.5:batch", "pricing": {"prompt": "0.000001", "completion": "0.000005"}},
    {"id": "acme/router", "pricing": {"prompt": "-1", "completion": "-1"}},
]}


def test_norm_model():
    assert prices.norm_model("anthropic/claude-opus-5.5") == "claude-opus-5-5"
    assert prices.norm_model("deepseek-v4.1-flash-free") == "deepseek-v4-1-flash"
    assert prices.norm_model("minimax/minimax-m3:free") == "minimax-m3"
    assert prices.norm_model("claude-haiku-4-5-20251001") == "claude-haiku-4-5"


def test_refresh_prefers_exact_id_and_skips_variants(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen(PAYLOAD))
    assert prices.refresh_prices(force=True)
    tbl, src, upd = prices.prices()
    assert src == "OpenRouter" and upd
    assert tbl["super-model-1-5"] == (2.0, 0.2, 10.0, 2.5)  # exact id wins over -contributor
    assert "router" not in tbl  # negative prices are ignored
    assert prices.price_for("super-model-1.5-free") == (2.0, 0.2, 10.0, 2.5)


def test_cache_is_reused_within_a_day(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen(PAYLOAD))
    assert prices.refresh_prices()
    assert not prices.refresh_prices()  # fresh cache: no request
    old = time.time() - 2 * 86400
    os.utime(prices.cache_file(), (old, old))
    assert prices.refresh_prices()


def test_no_network_falls_back_to_builtin(monkeypatch):
    def boom(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr("urllib.request.urlopen", boom)
    assert not prices.refresh_prices(force=True)
    tbl, src, _ = prices.prices()
    assert src == "builtin"
    assert prices.price_for("claude-opus-5-5")


def test_offline_mode_never_fetches(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr("urllib.request.urlopen", boom)
    config.OFFLINE = True
    assert not prices.refresh_prices(force=True)
