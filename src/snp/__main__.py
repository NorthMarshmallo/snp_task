"""Запуск расчёта всех кейсов из каталога CSV."""

import argparse
import sys
from pathlib import Path

from .input import InputError, load_data
from .output import print_case, print_rules
from .planner import plan_case


def main() -> int:
    """Прочитать аргументы, рассчитать кейсы и вернуть код завершения."""
    parser = argparse.ArgumentParser(description="План распределения по неделям")
    parser.add_argument("data_dir", type=Path, help="каталог с пятью CSV")
    args = parser.parse_args()
    try:
        data = load_data(args.data_dir)
    except InputError as exc:
        print(f"Ошибка входных данных: {exc}", file=sys.stderr)
        return 2
    for warning in data.warnings:
        print(f"Предупреждение: {warning}", file=sys.stderr)
    print_rules(data)
    has_missing = False
    for case in data.cases:
        has_missing = print_case(data, case, plan_case(data, case)) or has_missing
    return int(has_missing)


if __name__ == "__main__":
    raise SystemExit(main())
