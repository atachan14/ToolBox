from tools.clamp.logic import build_clamp, parse_value_text, resolve_output_unit, resolve_view_unit


def test_parse_value_text_accepts_number_and_unit():
    ok, parsed = parse_value_text(" 1.5rem ")

    assert ok is True
    assert parsed == (1.5, "rem")


def test_parse_value_text_rejects_invalid_text():
    ok, message = parse_value_text("abc")

    assert ok is False
    assert isinstance(message, str)
    assert message


def test_resolve_output_unit_prefers_input_unit():
    ok, unit = resolve_output_unit("px", "px", "rem")

    assert ok is True
    assert unit == "px"


def test_resolve_output_unit_rejects_mismatched_units():
    ok, message = resolve_output_unit("px", "rem", "")

    assert ok is False
    assert "単位" in message


def test_build_clamp_returns_expected_expression():
    ok, value = build_clamp((16, "px"), (32, "px"), 320, 1280)

    assert ok is True
    assert value == "clamp(16px, calc(10.67px + 1.67vw), 32px)"


def test_build_clamp_handles_decreasing_values():
    ok, value = build_clamp((32, "px"), (16, "px"), 320, 1280)

    assert ok is True
    assert value == "clamp(16px, calc(37.33px - 1.67vw), 32px)"


def test_build_clamp_handles_reversed_viewport_inputs():
    ok, value = build_clamp((32, "px"), (16, "px"), 1280, 320)

    assert ok is True
    assert value == "clamp(16px, calc(10.67px + 1.67vw), 32px)"


def test_build_clamp_uses_selected_unit_for_unitless_values():
    ok, value = build_clamp((10, ""), (20, ""), 320, 1280, selected_unit="rem")

    assert ok is True
    assert value == "clamp(10rem, calc(6.67rem + 1.04vw), 20rem)"


def test_build_clamp_rejects_same_viewport_width():
    ok, message = build_clamp((16, "px"), (32, "px"), 320, 320)

    assert ok is False
    assert isinstance(message, str)
    assert message


def test_resolve_view_unit_prefers_arbitrary_input_unit():
    ok, unit = resolve_view_unit("dvh", "", "vw")

    assert ok is True
    assert unit == "dvh"


def test_resolve_view_unit_rejects_mismatched_units():
    ok, message = resolve_view_unit("vw", "vh", "vw")

    assert ok is False
    assert isinstance(message, str)
    assert message


def test_resolve_view_unit_allows_blank_selector():
    ok, unit = resolve_view_unit("", "", "")

    assert ok is True
    assert unit == ""


def test_build_clamp_uses_arbitrary_view_unit():
    ok, value = build_clamp((16, "px"), (32, "px"), 320, 1280, view_unit="custom")

    assert ok is True
    assert value == "clamp(16px, calc(10.67px + 1.67custom), 32px)"
