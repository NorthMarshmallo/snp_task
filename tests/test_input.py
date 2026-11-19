from pathlib import Path
from shutil import copytree

import pytest

from snp.input import InputError, load_data


def test_original_files_are_read_and_extra_product_is_reported():
    """Лишний продукт сообщается и не влияет на план: иначе исходный X теряется молча."""
    data = load_data(Path("data"))
    assert len(data.cases) == 9
    assert any("X" in warning for warning in data.warnings)
    case = next(case for case in data.cases if case.case_id == "CASE_03")
    assert case.receipts[(2, "C")] == 180


def test_missing_input_is_rejected(tmp_path):
    """Отсутствующий CSV отклоняется: иначе расчёт начнётся с неполными данными."""
    with pytest.raises(InputError):
        load_data(tmp_path)


@pytest.mark.parametrize(
    ("filename", "old", "new"),
    [
        ("demand.csv", "CASE_01,1,R-1,1,30,0", "CASE_01,8,R-1,1,30,0"),
        ("demand.csv", "CASE_01,1,R-1,1,30,0", "CASE_01,1,R-1,1,30,31"),
        ("stock.csv", "CASE_01,P,90", "CASE_01,P,-90"),
    ],
)
def test_contradictory_data_is_rejected(tmp_path, filename, old, new):
    """Невозможные периоды и количества отклоняются: иначе расчёт примет противоречивый вход."""
    source = Path(__file__).resolve().parents[1] / "data"
    target = tmp_path / "data"
    copytree(source, target)
    path = target / filename
    content = path.read_text(encoding="utf-8")
    assert old in content
    path.write_text(content.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(InputError):
        load_data(target)
