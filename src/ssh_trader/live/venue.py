from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class Position:
    symbol: str
    venue: str
    side: Literal["long", "short"]
    quantity: float
    entry_price: float


@dataclass(frozen=True, slots=True)
class MarginStatus:
    equity: float
    gross_exposure: float
    maintenance_margin_ratio: float


@dataclass(frozen=True, slots=True)
class OrderRequest:
    client_order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    reduce_only: bool = False


@dataclass(frozen=True, slots=True)
class FillReport:
    order_id: str
    client_order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    requested_qty: float
    filled_qty: float
    fill_price: float
    mark_price: float
    slippage_bps: float
    status: Literal["filled", "partial", "rejected"]
    reason: str | None
    ts: datetime


class VenueAdapter(ABC):
    @abstractmethod
    def get_positions(self) -> list[Position]:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, request: OrderRequest) -> FillReport:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_mark_price(self, symbol: str) -> float:
        raise NotImplementedError

    @abstractmethod
    def get_funding_rate(self, symbol: str) -> float:
        raise NotImplementedError

    @abstractmethod
    def get_margin_status(self) -> MarginStatus:
        raise NotImplementedError
