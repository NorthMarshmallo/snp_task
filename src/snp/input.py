"""Чтение и проверка всех данных до начала расчёта."""

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import Case, Data, Request

ZERO = Decimal(0)


class InputError(ValueError):
    """Данные отсутствуют, имеют неверный формат или противоречат контракту."""


def read_csv(path: Path, columns: set[str]) -> list[dict[str, str]]:
    """Прочитать CSV и проверить обязательные столбцы и структуру строк."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if reader.fieldnames is None or not columns.issubset(reader.fieldnames):
                raise InputError(f"{path}: отсутствуют обязательные столбцы")
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise InputError(f"{path}: повторяются имена столбцов")
            rows = list(reader)
            if any(None in row or any(v is None for v in row.values()) for row in rows):
                raise InputError(f"{path}: некорректное число полей")
            return rows
    except (OSError, UnicodeError, csv.Error) as exc:
        raise InputError(f"{path}: {exc}") from exc


def number(value: str, field: str, *, integer: bool = False) -> Decimal:
    """Преобразовать неотрицательное число и при необходимости проверить целочисленность."""
    try:
        result = Decimal(value.strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise InputError(f"{field}: некорректное число {value!r}") from exc
    if not result.is_finite() or result < 0 or (integer and result != result.to_integral_value()):
        raise InputError(f"{field}: недопустимое значение {value!r}")
    return result


def required(value: str, field: str) -> str:
    """Проверить, что обязательная строка не пуста."""
    value = value.strip()
    if not value:
        raise InputError(f"{field}: пустое значение")
    return value


def load_data(directory: Path) -> Data:
    """Проверить все файлы и объединить строки в независимые кейсы."""
    bom = read_csv(directory / "bom.csv", {"component", "product", "qty_per_unit"})
    policies = read_csv(directory / "policies.csv", {"parameter", "value"})
    stock = read_csv(directory / "stock.csv", {"case_id", "product", "initial_qty"})
    receipts = read_csv(directory / "receipts.csv", {"case_id", "period", "product", "qty"})
    demand = read_csv(
        directory / "demand.csv", {"case_id", "period", "request_id", "priority", "qty", "min_lot"}
    )
    if len(bom) != 1:
        raise InputError("bom.csv: ожидается ровно одна пара компонента и продукта")
    component = required(bom[0]["component"], "component")
    product = required(bom[0]["product"], "product")
    factor = number(bom[0]["qty_per_unit"], "qty_per_unit")
    if component == product or not factor:
        raise InputError("bom.csv: продукт и компонент должны различаться, qty_per_unit > 0")
    params = {}
    for row in policies:
        key = required(row["parameter"], "parameter")
        if key in params:
            raise InputError(f"policies.csv: повтор параметра {key}")
        params[key] = row["value"]
    if not {"horizon", "assembly_lead_weeks", "assembly_multiple"} <= params.keys():
        raise InputError("policies.csv: отсутствует обязательный параметр")
    horizon = int(number(params["horizon"], "horizon", integer=True))
    lead = int(number(params["assembly_lead_weeks"], "assembly_lead_weeks", integer=True))
    multiple = number(params["assembly_multiple"], "assembly_multiple")
    if not horizon or not multiple:
        raise InputError("horizon и assembly_multiple должны быть больше нуля")
    cases = {}
    warnings = set()

    def get_case(row):
        """Найти кейс строки или создать пустой."""
        name = required(row["case_id"], "case_id")
        return cases.setdefault(name, {"stock": {}, "receipts": {}, "requests": []})

    def period(row):
        """Проверить номер недели в пределах горизонта."""
        value = int(number(row["period"], "period", integer=True))
        if value >= horizon:
            raise InputError(f"period {value} вне горизонта 0..{horizon - 1}")
        return value

    for row in stock:
        case = get_case(row)
        item = required(row["product"], "product")
        qty = number(row["initial_qty"], "initial_qty")
        if item not in {component, product}:
            warnings.add(f"Неиспользуемый запас: {item}")
            continue
        if item in case["stock"]:
            raise InputError(f"stock.csv: повтор запаса {row['case_id']}, {item}")
        case["stock"][item] = qty
    for row in receipts:
        case = get_case(row)
        week = period(row)
        item = required(row["product"], "product")
        qty = number(row["qty"], "receipt qty")
        if item not in {component, product}:
            warnings.add(f"Неиспользуемое поступление: {item}")
            continue
        key = (week, item)
        case["receipts"][key] = case["receipts"].get(key, ZERO) + qty
    for row_no, row in enumerate(demand, start=2):
        case = get_case(row)
        qty = number(row["qty"], "demand qty")
        lot = number(row["min_lot"], "min_lot")
        if lot > qty:
            raise InputError(f"demand.csv:{row_no}: min_lot больше qty")
        case["requests"].append(
            Request(
                period(row),
                required(row["request_id"], "request_id"),
                int(number(row["priority"], "priority", integer=True)),
                qty,
                lot,
                row_no,
            )
        )
    if not cases:
        raise InputError("Нет кейсов")
    return Data(
        horizon,
        multiple,
        lead,
        factor,
        component,
        product,
        [Case(name, **case) for name, case in sorted(cases.items())],
        sorted(warnings),
    )
