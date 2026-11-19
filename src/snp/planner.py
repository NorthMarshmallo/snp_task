"""Детерминированное распределение ресурсов во времени по приоритету."""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .models import Case, Data

ZERO = Decimal(0)


def plan_case(data: Data, case: Case) -> dict:
    """Запланировать раннюю сборку и зарезервировать продукт по приоритету."""
    total = sum((r.qty for r in case.requests), ZERO)
    need = max(ZERO, total - case.stock.get(data.product, ZERO))
    limit = (need / data.multiple).to_integral_value(rounding=ROUND_CEILING) * data.multiple
    made = ZERO
    component = case.stock.get(data.component, ZERO)
    product = case.stock.get(data.product, ZERO)
    arrivals = [ZERO] * data.horizon
    assemblies = [ZERO] * data.horizon
    components = []
    available = []
    for week in range(data.horizon):
        component += case.receipts.get((week, data.component), ZERO)
        product += case.receipts.get((week, data.product), ZERO) + arrivals[week]
        if week + data.lead < data.horizon:
            batches = (component / (data.factor * data.multiple)).to_integral_value(
                rounding=ROUND_FLOOR
            )
            amount = min(batches * data.multiple, limit - made)
            component -= amount * data.factor
            made += amount
            assemblies[week] = amount
            if data.lead == 0:
                product += amount
            else:
                arrivals[week + data.lead] += amount
        components.append(component)
        available.append(product)

    # Остатки после ранее сделанных резервирований, на конец каждой недели.
    allocations = {}
    capacities = {}
    ordered = sorted(
        case.requests, key=lambda r: (r.priority == 0, r.priority, r.period, r.request_id, r.row)
    )
    for request in ordered:
        capacity = min(available[request.period :])
        capacities[request.row] = capacity
        amount = min(request.qty, capacity)
        if amount < request.min_lot:
            amount = ZERO
        allocations[request.row] = amount
        for week in range(request.period, data.horizon):
            available[week] -= amount

    return {
        "assemblies": assemblies,
        "component_stock": components,
        "product_stock": available,
        "allocations": allocations,
        "capacities": capacities,
        "order": [request.row for request in ordered],
    }
