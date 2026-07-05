import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from tools.clamp.tool import Tab


def _app():
    return QApplication.instance() or QApplication([])


def test_clamp_restores_legacy_state_into_first_calculator(tmp_path):
    _app()
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "min_px": "16px",
                "min_view": "600dvh",
                "max_view": "994",
                "max_px": "32px",
                "result_unit": "px",
            }
        ),
        encoding="utf-8",
    )

    tool = Tab(tab_dir=tmp_path)
    calculators = tool._calculator_widgets()

    assert len(calculators) == 1
    assert calculators[0].min_view.text() == "600dvh"


def test_clamp_adds_and_persists_multiple_calculators(tmp_path):
    _app()
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    tool = Tab(tab_dir=tmp_path)

    tool._add_calculator("1400-1920", select=True)
    tool.calculator.min_view.setText("1400")
    tool.calculator.max_view.setText("1920")

    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert [item["name"] for item in saved["calculators"]] == ["1", "1400-1920"]
    assert saved["calculators"][1]["max_view"] == "1920"


def test_clamp_plus_tab_adds_a_uniquely_named_calculator(tmp_path):
    _app()
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    tool = Tab(tab_dir=tmp_path)

    assert tool.tabs.tabsClosable() is False
    tool._on_tab_clicked(tool.tabs.indexOf(tool._plus_widget))

    names = [
        tool.tabs.tabText(tool.tabs.indexOf(calculator))
        for calculator in tool._calculator_widgets()
    ]
    assert names == ["1", "2"]
    assert tool.tabs.currentWidget() is tool._calculator_widgets()[1]


def test_clamp_calculator_unit_defaults_and_blank_view_unit(tmp_path):
    _app()
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    tool = Tab(tab_dir=tmp_path)
    calculator = tool.calculator

    assert calculator.unit_toggle.currentData() == "px"
    assert calculator.view_unit_toggle.itemData(0) == ""
    assert calculator.view_unit_toggle.currentData() == "vw"

    calculator.set_result_unit("")
    calculator.set_view_unit("")
    calculator.min_px.setText("16")
    calculator.min_view.setText("320")
    calculator.max_view.setText("1280")
    calculator.max_px.setText("32")
    calculator.form_exe()
    assert calculator._current_result_text == "clamp(16, calc(10.67 + 1.67), 32)"

    calculator.reverse_input.setText(calculator._current_result_text)
    calculator.reverse_exe()
    assert calculator.view_unit_toggle.currentData() == ""


def test_clamp_can_close_all_calculators_and_restore_plus_only_state(tmp_path):
    _app()
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    tool = Tab(tab_dir=tmp_path)

    tool._close_calculator(0)

    assert tool._calculator_widgets() == []
    assert tool.tabs.currentWidget() is tool._plus_widget
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert saved["calculators"] == []

    restored = Tab(tab_dir=tmp_path)
    assert restored._calculator_widgets() == []
    restored._on_tab_clicked(restored.tabs.indexOf(restored._plus_widget))
    assert restored.tabs.tabText(0) == "1"


def test_clamp_uses_and_reverses_arbitrary_view_units(tmp_path):
    _app()
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    tool = Tab(tab_dir=tmp_path)
    calculator = tool.calculator

    calculator.min_px.setText("16px")
    calculator.min_view.setText("600custom")
    calculator.max_view.setText("1000")
    calculator.max_px.setText("32px")
    calculator.form_exe()

    assert "custom" in calculator._current_result_text

    calculator.reverse_input.setText("clamp(16px, calc(8px + 2dvh), 32px)")
    calculator.reverse_exe()

    assert calculator.min_view.text().endswith("dvh")
    assert calculator.max_view.text().endswith("dvh")
