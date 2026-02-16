from ssh_trader.data.hyperliquid_history import merge_history_rows, parse_time_ms, ts_ms_to_utc_iso


def test_parse_time_ms_and_iso_roundtrip() -> None:
    ts = parse_time_ms("2024-01-01T00:00:00Z")
    assert ts > 0
    assert ts_ms_to_utc_iso(ts).startswith("2024-01-01T00:00:00")


def test_merge_history_uses_last_known_funding() -> None:
    candles = [
        (1_000, 1.0, 1.1, 0.9, 1.0, 10.0),
        (2_000, 1.0, 1.1, 0.9, 1.0, 10.0),
        (3_000, 1.0, 1.1, 0.9, 1.0, 10.0),
    ]
    funding = [(1_500, 0.01), (2_500, -0.02)]
    rows = merge_history_rows(candles=candles, funding=funding, default_open_interest=5.0)
    assert [r.funding for r in rows] == [0.0, 0.01, -0.02]
    assert all(r.open_interest == 5.0 for r in rows)
