from ssh_trader.live.hyperliquid_stub import HyperliquidStubAdapter, HyperliquidStubConfig
from ssh_trader.live.venue import OrderRequest


def test_stub_order_and_partial_fill() -> None:
    venue = HyperliquidStubAdapter(
        HyperliquidStubConfig(
            symbol="BTC-PERP",
            initial_mark_price=100.0,
            initial_equity=10_000.0,
            max_fill_ratio=0.5,
            slippage_bps_at_1x_notional=10.0,
        )
    )
    venue.set_market(mark_price=100.0, funding_rate=0.001)
    rep = venue.place_order(
        OrderRequest(client_order_id="o1", symbol="BTC-PERP", side="buy", quantity=2.0)
    )
    assert rep.status == "partial"
    assert rep.filled_qty == 1.0
    assert rep.fill_price >= rep.mark_price
    pos = venue.get_positions()
    assert len(pos) == 1
    assert pos[0].side == "long"
    assert venue.get_funding_rate("BTC-PERP") == 0.001
