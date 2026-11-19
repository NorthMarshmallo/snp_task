"""Структуры входных данных для независимых кейсов."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Request:
    """Отдельная строка спроса с номером исходной строки CSV."""

    period: int
    request_id: str
    priority: int
    qty: Decimal
    min_lot: Decimal
    row: int


@dataclass(frozen=True)
class Case:
    """Запасы, поступления и заявки одного независимого кейса."""

    case_id: str
    stock: dict[str, Decimal]
    receipts: dict[tuple[int, str], Decimal]
    requests: list[Request]


@dataclass(frozen=True)
class Data:
    """Общие правила, кейсы и предупреждения о входных данных."""

    horizon: int
    multiple: Decimal
    lead: int
    factor: Decimal
    component: str
    product: str
    cases: list[Case]
    warnings: list[str]
