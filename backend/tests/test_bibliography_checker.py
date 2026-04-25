"""Tests for UC 3.1 bibliography freshness checker."""

from __future__ import annotations

from services.bibliography_checker import check_bibliography


SAMPLE_MD = """
## 8. Conținut

### Bibliografie

1. Author A, *Old Book*, Publisher, 1985.
2. Author B, *Newer Book*, Publisher, 2024.
3. Author C, *Untimed Book*, Publisher (no year here).
4. Author D, *Online*, 2023. https://example.com/x

### Bibliografie

1. Author E, *Mid Book*, Publisher, 2010 (reeditată în 2022).

## 9. Coroborare
"""


def test_finds_two_bibliography_sections():
    report = check_bibliography(SAMPLE_MD, current_year=2025)
    assert report.total_entries == 5
    sections = {e.section_index for e in report.entries}
    assert sections == {0, 1}


def test_flags_stale_entries():
    report = check_bibliography(SAMPLE_MD, current_year=2025, max_age_years=5)
    stale = [e for e in report.entries if "stale" in e.issues]
    # Only the 1985 entry is stale; 2024/2023 are fresh, the "1979 reeditată
    # 2022" entry uses 2022 as latest_year (3yo → fresh).
    assert len(stale) == 1
    assert stale[0].latest_year == 1985


def test_flags_undated_entries():
    report = check_bibliography(SAMPLE_MD, current_year=2025)
    undated = [e for e in report.entries if "no_year" in e.issues]
    assert len(undated) == 1
    assert "Untimed Book" in undated[0].text


def test_extracts_urls():
    report = check_bibliography(SAMPLE_MD, current_year=2025)
    with_urls = [e for e in report.entries if e.urls]
    assert len(with_urls) == 1
    assert with_urls[0].urls == ["https://example.com/x"]


def test_uses_latest_year_when_multiple_present():
    report = check_bibliography(SAMPLE_MD, current_year=2025)
    mid = next(e for e in report.entries if "Mid Book" in e.text)
    assert mid.latest_year == 2022
    assert mid.age_years == 3
    assert "stale" not in mid.issues


def test_no_bibliography_section():
    report = check_bibliography("Some random text without any sections.", current_year=2025)
    assert report.total_entries == 0
    assert "Nu s-au găsit" in report.summary
