from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from .venue import FillReport, MarginStatus, OrderRequest, Position, VenueAdapter


@dataclass(frozen=True, slots=True)
class HyperliquidStubConfig:
    symbol: str = "BTC-PERP"
    venue: str = "hyperliquid_stub"
    latency_ms: int = 0
    apply_latency: bool = False
    slippage_bps_at_1x_notional: float = 10.0
    max_fill_ratio: float = 1.0
    initial_mark_price: float = 50_000.0
    initial_funding_rate: float = 0.0
    initial_equity: float = 1_000_000.0
    maintenance_margin_ratio: float = 0.05

    def __post_init__(self) -> None:
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be >= 0")
        if not (0.0 < self.max_fill_ratio <= 1.0):
            raise ValueError("max_fill_ratio must be in (0, 1]")
        if self.initial_mark_price <= 0.0 or not math.isfinite(self.initial_mark_price):
            raise ValueError("initial_mark_price must be finite and positive")
        if self.initial_equity <= 0.0 or not math.isfinite(self.initial_equity):
            raise ValueError("initial_equity must be finite and positive")
        if self.slippage_bps_at_1x_notional < 0.0 or not math.isfinite(
            self.slippage_bps_at_1x_notional
        ):
            raise ValueError("slippage_bps_at_1x_notional must be finite and >= 0")


class HyperliquidStubAdapter(VenueAdapter):
    def __init__(self, config: HyperliquidStubConfig | None = None) -> None:
        self._cfg = config if config is not None else HyperliquidStubConfig()
        self._mark_price = self._cfg.initial_mark_price
        self._funding_rate = self._cfg.initial_funding_rate
        self._equity = self._cfg.initial_equity
        self._position_qty = 0.0
        self._order_num = 0

    def set_market(self, *, mark_price: float, funding_rate: float) -> None:
        if mark_price <= 0.0 or not math.isfinite(mark_price):
            raise ValueError("mark_price must be finite and positive")
        if not math.isfinite(funding_rate):
            raise ValueError("funding_rate must be finite")
        self._mark_price = mark_price
        self._funding_rate = funding_rate

    def get_positions(self) -> list[Position]:
        if self._position_qty == 0.0:
            return []
        side: Literal["long", "short"] = "long" if self._position_qty > 0 else "short"
        return [
            Position(
                symbol=self._cfg.symbol,
                venue=self._cfg.venue,
                side=side,
                quantity=abs(self._position_qty),
                entry_price=self._mark_price,
            )
        ]

    def place_order(self, request: OrderRequest) -> FillReport:
        if self._cfg.apply_latency and self._cfg.latency_ms > 0:
            time.sleep(self._cfg.latency_ms / 1000.0)

        self._order_num += 1
        order_id = f"hls-{self._order_num}"
        qty = max(0.0, request.quantity)
        filled_qty = qty * self._cfg.max_fill_ratio
        status: Literal["filled", "partial", "rejected"] = (
            "filled" if filled_qty == qty else "partial"
        )
        reason = None

        notional = filled_qty * self._mark_price
        notional_to_equity = (notional / self._equity) if self._equity > 0 else 0.0
        slippage_bps = self._cfg.slippage_bps_at_1x_notional * notional_to_equity
        slip_mult = slippage_bps / 1e4
        if request.side == "buy":
            fill_price = self._mark_price * (1.0 + slip_mult)
            self._position_qty += filled_qty
        else:
            fill_price = self._mark_price * (1.0 - slip_mult)
            self._position_qty -= filled_qty

        return FillReport(
            order_id=order_id,
            client_order_id=request.client_order_id,
            symbol=request.symbol,
            side=request.side,
            requested_qty=qty,
            filled_qty=filled_qty,
            fill_price=fill_price,
            mark_price=self._mark_price,
            slippage_bps=slippage_bps,
            status=status,
            reason=reason,
            ts=datetime.now(tz=timezone.utc),
        )

    def cancel_order(self, order_id: str) -> bool:
        _ = order_id
        return True

    def get_mark_price(self, symbol: str) -> float:
        if symbol != self._cfg.symbol:
            raise ValueError(f"unsupported symbol: {symbol}")
        return self._mark_price

    def get_funding_rate(self, symbol: str) -> float:
        if symbol != self._cfg.symbol:
            raise ValueError(f"unsupported symbol: {symbol}")
        return self._funding_rate

    def get_margin_status(self) -> MarginStatus:
        gross = abs(self._position_qty * self._mark_price)
        return MarginStatus(
            equity=self._equity,
            gross_exposure=gross,
            maintenance_margin_ratio=self._cfg.maintenance_margin_ratio,
        )
