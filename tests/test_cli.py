import os
import subprocess
import sys
from pathlib import Path


def test_cli_reports_success_and_invalid_input(tmp_path):
    """Полностью покрытый спрос даёт код 0, отсутствие обязательного файла - код 2: согласно
    правилам задачи."""
    source = Path(__file__).resolve().parents[1] / "src"
    env = dict(os.environ, PYTHONPATH=str(source))
    files = {
        "bom.csv": "component,product,qty_per_unit\nC,P,2\n",
        "policies.csv": "parameter,value\nassembly_multiple,10\nassembly_lead_weeks,1\nhorizon,2\n",
        "stock.csv": "case_id,product,initial_qty\nA,P,10\nA,C,0\n",
        "receipts.csv": "case_id,period,product,qty\n",
        "demand.csv": "case_id,period,request_id,priority,qty,min_lot\nA,1,R1,1,10,0\n",
    }
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "snp", str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "полностью покрыто: 1" in result.stdout
    assert "неделя 1, приоритет 1, спрос 10, min_lot 0, доступно 10, отгружено 10" in result.stdout
    (tmp_path / "bom.csv").unlink()
    result = subprocess.run(
        [sys.executable, "-m", "snp", str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Ошибка входных данных" in result.stderr


def test_cli_reports_shortage_on_original_data():
    """Недостача возвращает код 1 и реестр: иначе потребитель не узнает о ней."""
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(root / "src"))
    result = subprocess.run(
        [sys.executable, "-m", "snp", str(root / "data")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Непокрытый спрос:" in result.stdout
    assert "CASE_09" in result.stdout
    assert result.stdout.count("Правило: приоритет 1 выше 2") == 1
    assert result.stdout.index("Правило:") < result.stdout.index("Кейс CASE_01")
