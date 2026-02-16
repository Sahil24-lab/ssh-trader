from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from ssh_trader.live.venue import FillReport, OrderRequest, VenueAdapter
from ssh_trader.risk.governor import RiskGovernor


@dataclass(frozen=True, slots=True)
class ControlConfig:
    symbol: str = "BTC-PERP"
    rebalance_interval_bars: int = 1
    max_slippage_bps: float = 30.0
    min_order_qty: float = 0.0
    oracle_divergence_bps: float = 50.0
    mev_mode: Literal["placeholder", "none"] = "placeholder"

    def __post_init__(self) -> None:
        if self.rebalance_interval_bars <= 0:
            raise ValueError("rebalance_interval_bars must be positive")
        if self.max_slippage_bps < 0.0 or not math.isfinite(self.max_slippage_bps):
            raise ValueError("max_slippage_bps must be finite and >= 0")
        if self.min_order_qty < 0.0 or not math.isfinite(self.min_order_qty):
            raise ValueError("min_order_qty must be finite and >= 0")
        if self.oracle_divergence_bps < 0.0 or not math.isfinite(self.oracle_divergence_bps):
            raise ValueError("oracle_divergence_bps must be finite and >= 0")
        if self.mev_mode not in ("placeholder", "none"):
            raise ValueError("mev_mode must be placeholder or none")


@dataclass(frozen=True, slots=True)
class TargetExposure:
    target_perp_qty: float
    directional_requested: bool


@dataclass(frozen=True, slots=True)
class ControlDecision:
    intended_order: OrderRequest | None
    hypothetical_fill: FillReport | None
    slippage_estimate_bps: float
    regime_state: str
    skipped: bool
    reason: str | None
    route_hint: str


class ControlEngine:
    def __init__(
        self, *, venue: VenueAdapter, risk: RiskGovernor, config: ControlConfig | None = None
    ) -> None:
        self._venue = venue
        self._risk = risk
        self._cfg = config if config is not None else ControlConfig()
        self._bar_idx = 0
        self._peak_equity = 0.0
        self._pending_qty = 0.0
        self._order_num = 0

    def _next_id(self) -> str:
        self._order_num += 1
        return f"ctl-{self._order_num}"

    def _route_hint(self) -> str:
        if self._cfg.mev_mode == "placeholder":
            return "mev_guard_placeholder"
        return "direct"

    def _estimate_slippage_bps(self, qty: float, mark: float, equity: float) -> float:
        if equity <= 0.0:
            return 0.0
        notional_frac = abs(qty * mark) / equity
        return notional_frac * self._cfg.max_slippage_bps

    def on_bar(
        self,
        *,
        ts: datetime,
        target: TargetExposure,
        regime_state: str,
        oracle_price: float,
        vol_pct: float | None,
        vol_spike_active: bool,
    ) -> ControlDecision:
        mark = self._venue.get_mark_price(self._cfg.symbol)
        margin = self._venue.get_margin_status()
        if self._peak_equity <= 0.0:
            self._peak_equity = margin.equity
        if margin.equity > self._peak_equity:
            self._peak_equity = margin.equity

        self._bar_idx += 1
        if (self._bar_idx - 1) % self._cfg.rebalance_interval_bars != 0:
            return ControlDecision(
                intended_order=None,
                hypothetical_fill=None,
                slippage_estimate_bps=0.0,
                regime_state=regime_state,
                skipped=True,
                reason="rebalance_wait",
                route_hint=self._route_hint(),
            )

        if oracle_price <= 0.0 or mark <= 0.0:
            return ControlDecision(
                intended_order=None,
                hypothetical_fill=None,
                slippage_estimate_bps=0.0,
                regime_state=regime_state,
                skipped=True,
                reason="invalid_price",
                route_hint=self._route_hint(),
            )

        div_bps = abs(mark - oracle_price) / oracle_price * 1e4
        if div_bps > self._cfg.oracle_divergence_bps:
            return ControlDecision(
                intended_order=None,
                hypothetical_fill=None,
                slippage_estimate_bps=0.0,
                regime_state=regime_state,
                skipped=True,
                reason="oracle_divergence",
                route_hint=self._route_hint(),
            )

        decision = self._risk.decide(
            nav=margin.equity,
            peak_nav=self._peak_equity,
            vol_pct=vol_pct,
            requested_directional=target.directional_requested,
        )
        if vol_spike_active:
            return ControlDecision(
                intended_order=None,
                hypothetical_fill=None,
                slippage_estimate_bps=0.0,
                regime_state=regime_state,
                skipped=True,
                reason="vol_spike_active",
                route_hint=self._route_hint(),
            )
        if decision.mode == "flat":
            target_qty = 0.0
        elif decision.mode == "carry_only" and target.directional_requested:
            target_qty = 0.0
        else:
            target_qty = target.target_perp_qty

        positions = self._venue.get_positions()
        cur_qty = 0.0
        for pos in positions:
            signed = pos.quantity if pos.side == "long" else -pos.quantity
            if pos.symbol == self._cfg.symbol:
                cur_qty += signed

        qty_delta = (target_qty - cur_qty) + self._pending_qty
        if abs(qty_delta) <= self._cfg.min_order_qty:
            self._pending_qty = 0.0
            return ControlDecision(
                intended_order=None,
                hypothetical_fill=None,
                slippage_estimate_bps=0.0,
                regime_state=regime_state,
                skipped=True,
                reason="below_min_qty",
                route_hint=self._route_hint(),
            )

        slippage_est = self._estimate_slippage_bps(qty_delta, mark, margin.equity)
        if slippage_est > self._cfg.max_slippage_bps:
            return ControlDecision(
                intended_order=None,
                hypothetical_fill=None,
                slippage_estimate_bps=slippage_est,
                regime_state=regime_state,
                skipped=True,
                reason="slippage_guard",
                route_hint=self._route_hint(),
            )

        side: Literal["buy", "sell"] = "buy" if qty_delta > 0 else "sell"
        order = OrderRequest(
            client_order_id=self._next_id(),
            symbol=self._cfg.symbol,
            side=side,
            quantity=abs(qty_delta),
            reduce_only=False,
        )
        fill = self._venue.place_order(order)
        self._pending_qty = 0.0
        if fill.status == "partial":
            remaining = fill.requested_qty - fill.filled_qty
            self._pending_qty = remaining if side == "buy" else -remaining

        return ControlDecision(
            intended_order=order,
            hypothetical_fill=fill,
            slippage_estimate_bps=slippage_est,
            regime_state=regime_state,
            skipped=False,
            reason=None,
            route_hint=self._route_hint(),
        )
