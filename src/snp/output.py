"""Вывод планов и непокрытого спроса в читаемом виде."""

from .models import Case, Data


def print_rules(data: Data) -> None:
    """Один раз вывести общие правила распределения и сборки."""
    print(
        "Правило: приоритет 1 выше 2; приоритет 0 — после положительных.\n"
        "При равном приоритете: неделя, идентификатор, строка CSV.\n"
        "Недели нумеруются с 0; заявки показаны в порядке распределения.\n"
        "Доступно — максимум с учётом предыдущих резервирований и будущих недель."
    )
    print(
        f"Сборка запускается по возможности заранее, кратно {data.multiple}; "
        f"продукт доступен через {data.lead} нед."
    )


def print_case(data: Data, case: Case, plan: dict) -> bool:
    """Вывести результат кейса и вернуть признак наличия недостачи."""
    print(f"\nКейс {case.case_id}")
    print("Отгрузки:")
    missing = []
    requests_by_row = {request.row: request for request in case.requests}
    for row in plan["order"]:
        request = requests_by_row[row]
        amount = plan["allocations"][request.row]
        capacity = plan["capacities"][request.row]
        print(
            f"  {request.request_id} (строка {request.row}): неделя {request.period}, "
            f"приоритет {request.priority}, спрос {request.qty}, min_lot {request.min_lot}, "
            f"доступно {capacity}, отгружено {amount}"
        )
        if amount < request.qty:
            missing.append((request, request.qty - amount, amount))
    print(f"Неделя | Сборка | Остаток {data.product} | Остаток {data.component}")
    for week in range(data.horizon):
        print(
            f"{week:>6} | {plan['assemblies'][week]} | {plan['product_stock'][week]} | {plan['component_stock'][week]}"
        )
    print("Непокрытый спрос:")
    if not missing:
        print("  нет")
    for request, qty, amount in missing:
        capacity = plan["capacities"][request.row]
        if capacity < request.min_lot:
            reason = f"доступно {capacity}, меньше минимальной партии {request.min_lot}"
        else:
            reason = f"доступно {capacity} после предыдущих резервирований"
        print(
            f"  {request.request_id} (строка {request.row}, неделя {request.period}): {qty} — {reason}"
        )
    print(
        f"Всего заявок: {len(case.requests)}; полностью покрыто: {len(case.requests) - len(missing)}; не полностью покрыто: {len(missing)}"
    )
    return bool(missing)
