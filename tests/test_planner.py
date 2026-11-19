from decimal import Decimal as D
from pathlib import Path

from snp.input import load_data
from snp.models import Case, Data, Request
from snp.planner import plan_case


def setup(requests, *, stock="0", component="0", receipts=None, lead=1, horizon=4):
    """Создать небольшой независимый кейс и общие настройки."""
    case = Case("test", {"P": D(stock), "C": D(component)}, receipts or {}, requests)
    data = Data(horizon, D(10), lead, D(2), "C", "P", [case], [])
    return data, case


def req(row, period, priority, qty, lot="0"):
    """Создать заявку для проверки планировщика."""
    return Request(period, f"R{row}", priority, D(qty), D(lot), row)


# Обязательные ограничения условия


def test_future_high_priority_reserves_shared_stock():
    """Будущая важная заявка резервирует общий запас: иначе ранняя заберёт его."""
    data, case = setup([req(1, 0, 2, "10"), req(2, 2, 1, "10")], stock="10")
    plan = plan_case(data, case)
    assert plan["allocations"] == {2: D(10), 1: D(0)}
    assert all(x >= 0 for x in plan["product_stock"])


def test_assembly_lead_and_batch():
    """Сборка списывает компонент и доступна через срок: иначе план будет физически невозможным."""
    data, case = setup([req(1, 0, 1, "7"), req(2, 1, 1, "7")], component="20")
    plan = plan_case(data, case)
    assert plan["assemblies"] == [D(10), D(0), D(0), D(0)]
    assert plan["allocations"] == {1: D(0), 2: D(7)}
    assert plan["component_stock"][0] == 0
    assert plan["product_stock"][1] == 3


def test_same_week_receipts_and_zero_lead_are_available():
    """Поступление и сборка с нулевым сроком доступны в ту же неделю: иначе теряется спрос."""
    data, case = setup([req(1, 1, 1, "15")], receipts={(1, "C"): D(20), (1, "P"): D(5)}, lead=0)
    plan = plan_case(data, case)
    assert plan["assemblies"][1] == 10
    assert plan["allocations"][1] == 15
    assert plan["component_stock"][1] == 0


def test_late_receipt_cannot_cover_earlier_request():
    """Позднее поступление не покрывает раннюю заявку: иначе план нарушит сроки."""
    data, case = setup([req(1, 1, 1, "10")], receipts={(2, "P"): D(10)})
    assert plan_case(data, case)["allocations"][1] == 0


def test_original_cases_obey_weekly_balances_and_shipment_limits():
    """Балансы и партии соблюдаются во всех исходных кейсах: иначе план неисполним."""
    data = load_data(Path(__file__).resolve().parents[1] / "data")
    for case in data.cases:
        plan = plan_case(data, case)
        component = case.stock.get(data.component, D(0))
        product = case.stock.get(data.product, D(0))
        for week in range(data.horizon):
            assembly = plan["assemblies"][week]
            assert assembly >= 0 and assembly % data.multiple == 0
            component += case.receipts.get((week, data.component), D(0)) - assembly * data.factor
            finished_week = week - data.lead
            finished = plan["assemblies"][finished_week] if finished_week >= 0 else D(0)
            shipped = sum(
                (plan["allocations"][r.row] for r in case.requests if r.period == week), D(0)
            )
            product += case.receipts.get((week, data.product), D(0)) + finished - shipped
            assert component == plan["component_stock"][week] >= 0
            assert product == plan["product_stock"][week] >= 0
        for request in case.requests:
            shipped = plan["allocations"][request.row]
            assert shipped == 0 or request.min_lot <= shipped <= request.qty


# Выбранная политика и допущения, требующие согласования


def test_future_receipt_frees_early_stock():
    """Позднее поступление покрывает будущую заявку: иначе ранний запас удерживается зря."""
    data, case = setup(
        [req(1, 0, 2, "10"), req(2, 2, 1, "10")], stock="10", receipts={(2, "P"): D(10)}
    )
    assert plan_case(data, case)["allocations"] == {2: D(10), 1: D(10)}


def test_minimum_lot_allows_lower_priority_when_high_cannot_ship():
    """Объём меньше min_lot не отгружается: иначе нарушается минимальная партия."""
    data, case = setup([req(1, 1, 1, "20", "10"), req(2, 1, 2, "8")], stock="8")
    assert plan_case(data, case)["allocations"] == {1: D(0), 2: D(8)}


def test_zero_priority_last_and_decimal_deterministic():
    """Нулевой приоритет последний, дроби сохраняются: иначе нарушатся выбранные правила."""
    data, case = setup([req(1, 1, 0, "2.5"), req(2, 1, 1, "2.5")], stock="3.5")
    first = plan_case(data, case)
    assert first["allocations"] == {2: D("2.5"), 1: D("1.0")}
    assert first == plan_case(data, case)


def test_equal_priority_serves_earlier_request_first():
    """При равном приоритете ранняя заявка первая: иначе изменится выбранная политика."""
    data, case = setup([req(1, 2, 1, "10", "5"), req(2, 1, 1, "10", "5")], stock="10")
    assert plan_case(data, case)["allocations"] == {2: D(10), 1: D(0)}


def test_equal_priority_allocates_available_partial_amount():
    """Частичная партия не меньше min_lot отгружается: иначе допустимый спрос останется непокрыт."""
    data, case = setup([req(1, 1, 1, "10", "5"), req(2, 2, 1, "10", "5")], stock="15")
    assert plan_case(data, case)["allocations"] == {1: D(10), 2: D(5)}


def test_equal_priority_and_week_use_request_id_for_tie():
    """При одинаковой неделе побеждает меньший идентификатор: иначе ничья изменит план."""
    data, case = setup([req(9, 1, 1, "10"), req(2, 1, 1, "10")], stock="10")
    assert plan_case(data, case)["allocations"] == {2: D(10), 9: D(0)}


def test_repeated_request_id_uses_source_row_for_tie():
    """Строка CSV разрешает полную ничью: иначе повторные идентификаторы смешаются."""
    requests = [Request(1, "R", 1, D(10), D(0), row) for row in (9, 2)]
    data, case = setup(requests, stock="10")
    assert plan_case(data, case)["allocations"] == {2: D(10), 9: D(0)}


def test_partial_high_priority_precedes_lower_priority():
    """Частично покрываем важную заявку раньше менее важной: иначе нарушится выбранная политика."""
    data, case = setup([req(1, 1, 1, "20", "5"), req(2, 1, 2, "10")], stock="10")
    assert plan_case(data, case)["allocations"] == {1: D(10), 2: D(0)}
