"""Value parsing: codes and blanks become null + flags, never 0; odd formats fail loudly."""
import pytest

from pipeline import parse


@pytest.mark.parametrize("raw,code", [("SP", "SP"), ("N/R", "N/R"), ("N/D", "N/D"), ("NA", "NA"), (" n/r ", "N/R"), (None, "BLANK"), ("", "BLANK"), ("  ", "BLANK")])
def test_codes_become_null_with_code(raw, code):
    v, c = parse.parse_pct(raw, context="t")
    assert v is None
    assert c == code


@pytest.mark.parametrize("raw", ["SP", "N/R", "<10"])
def test_suppressed_flags(raw):
    f = parse.flags(parse.code_of(raw))
    assert f["suppressed"] is True
    assert f["small_cohort"] is True


def test_blank_is_not_zero_and_not_suppressed():
    v, c = parse.parse_pct(None, context="t")
    assert v is None and v != 0
    assert parse.flags(c)["suppressed"] is False


@pytest.mark.parametrize("raw,val", [("94%", 94), ("94 %", 94), ("0%", 0), ("100%", 100), ("72.5%", 72.5)])
def test_percent_strings(raw, val):
    assert parse.parse_pct(raw, context="t") == (val, None)


def test_bare_number_needs_a_declared_mode():
    with pytest.raises(parse.UnknownToken):
        parse.parse_pct(94, context="t")
    with pytest.raises(parse.UnknownToken):
        parse.parse_pct("94", context="t")


def test_whole_and_fraction_modes():
    assert parse.parse_pct("94", context="t", numeric="whole") == (94, None)
    assert parse.parse_pct(1, context="t", numeric="whole") == (1, None)
    assert parse.parse_pct(0.73, context="t", numeric="fraction") == (73, None)
    assert parse.parse_pct(1, context="t", numeric="fraction") == (100, None)
    assert parse.parse_pct(0.05, context="t", numeric="fraction") == (5, None)
    with pytest.raises(parse.UnknownToken):
        parse.parse_pct(0.5, context="t", numeric="whole")
    with pytest.raises(parse.UnknownToken):
        parse.parse_pct(150, context="t", numeric="fraction")


def test_unknown_token_fails_loudly():
    with pytest.raises(parse.UnknownToken):
        parse.parse_pct("about half", context="t")
    with pytest.raises(parse.UnknownToken):
        parse.parse_pct("140%", context="t")


@pytest.mark.parametrize("raw,val", [("155", 155), ("1,336", 1336), (42, 42), (42.0, 42)])
def test_counts(raw, val):
    assert parse.parse_count(raw, context="t") == (val, None)


def test_count_codes():
    assert parse.parse_count("<10", context="t") == (None, "<10")
    assert parse.parse_count("", context="t") == (None, "BLANK")
    with pytest.raises(parse.UnknownToken):
        parse.parse_count("12.5", context="t")


def test_fractions_for_board_indicators():
    assert parse.parse_fraction(0.77, context="t") == (77, None)
    assert parse.parse_fraction(0.734, context="t") == (73.4, None)
    assert parse.parse_fraction(-0.006, context="t") == (-0.6, None)
    assert parse.parse_fraction("N/A", context="t") == (None, "N/A")
    assert parse.parse_fraction("-", context="t") == (None, "-")


def test_postal_and_fsa():
    assert parse.norm_postal("p6a 3m7") == "P6A3M7"
    assert parse.norm_postal("P6A3M") is None
    assert parse.fsa_of("P6A3M7") == "P6A"
