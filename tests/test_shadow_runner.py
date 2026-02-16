from datetime import datetime, timedelta, timezone

from ssh_trader.data.model import OHLCVFrame
from ssh_trader.live.shadow_runner import ShadowRunnerConfig, run_shadow


def test_shadow_runner_logs_expected_fields() -> None:
    ts0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    close = [100.0 + i * 0.5 for i in range(48)]
    frame = OHLCVFrame(
        ts=[ts0 + timedelta(hours=i) for i in range(len(close))],
        open=list(close),
        high=[c * 1.01 for c in close],
        low=[c * 0.99 for c in close],
        close=close,
        volume=[1.0] * len(close),
        funding=[0.0] * len(close),
    )
    logs = run_shadow(
        frame,
        config=ShadowRunnerConfig(
            symbol="BTC-PERP",
            target_directional_vol=0.2,
            vol_spike_threshold=0.95,
        ),
    )
    assert len(logs) == len(close)
    first = logs[0]
    assert "timestamp" in first
    assert "intended_order" in first
    assert "hypothetical_fill" in first
    assert "slippage_estimate_bps" in first
    assert "regime" in first
