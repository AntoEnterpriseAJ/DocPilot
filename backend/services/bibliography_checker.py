"""UC 3.1 — Bibliography freshness & link liveness checks for a Fișa Disciplinei.

Parses the "Bibliografie" sections from the FD's markdown/text body and
flags entries that are older than 5 years or whose URLs return non-2xx
responses.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Literal

from pydantic import BaseModel

from schemas.extraction import ExtractedDocument

Severity = Literal["error", "warning", "info"]

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_URL_RE = re.compile(r"https?://[^\s\)\]<>]+", re.IGNORECASE)
_BIB_HEADING_RE = re.compile(
    r"^\s*(?:#+\s*)?Bibliografie\b[^\n]*$", re.IGNORECASE | re.MULTILINE
)
_NEXT_HEADING_RE = re.compile(r"^\s*(?:#+\s+|\d+(?:\.\d+)*\s+\w)", re.MULTILINE)
_ENTRY_PREFIX_RE = re.compile(r"^\s*(?:\d+\.|[-*])\s+", re.MULTILINE)


class BibliographyEntry(BaseModel):
    section_index: int
    entry_index: int
    text: str
    latest_year: int | None = None
    urls: list[str] = []
    age_years: int | None = None
    issues: list[str] = []


class BibliographyIssue(BaseModel):
    severity: Severity
    code: str
    message: str
    section_index: int
    entry_index: int
    entry_text: str


class BibliographyReport(BaseModel):
    entries: list[BibliographyEntry]
    issues: list[BibliographyIssue]
    total_entries: int
    fresh_entries: int
    stale_entries: int
    undated_entries: int
    summary: str


# --- parsing helpers -------------------------------------------------------


def _find_bibliography_blocks(text: str) -> list[str]:
    """Return the body text of each Bibliografie section."""
    blocks: list[str] = []
    for m in _BIB_HEADING_RE.finditer(text):
        start = m.end()
        # Find next heading (markdown # or numbered section like "9.").
        rest = text[start:]
        next_m = _NEXT_HEADING_RE.search(rest)
        end = start + next_m.start() if next_m else len(text)
        block = text[start:end].strip()
        if block:
            blocks.append(block)
    return blocks


def _split_entries(block: str) -> list[str]:
    """Split a Bibliografie block into entries by leading "N." markers."""
    # Find positions of numbered/bulleted prefixes.
    matches = list(_ENTRY_PREFIX_RE.finditer(block))
    if not matches:
        # Fall back to non-empty lines.
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        return lines
    entries: list[str] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        chunk = block[start:end].strip()
        # Collapse internal whitespace/newlines.
        chunk = re.sub(r"\s+", " ", chunk)
        if chunk:
            entries.append(chunk)
    return entries


def _latest_year(text: str) -> int | None:
    years = [int(m.group(0)) for m in _YEAR_RE.finditer(text)]
    return max(years) if years else None


def _extract_urls(text: str) -> list[str]:
    return [m.group(0).rstrip(".,;") for m in _URL_RE.finditer(text)]


# --- public API ------------------------------------------------------------


def check_bibliography(
    text: str,
    *,
    current_year: int | None = None,
    max_age_years: int = 5,
    check_urls: bool = False,
    url_timeout_seconds: float = 5.0,
) -> BibliographyReport:
    """Parse and assess the freshness of bibliography entries in an FD.

    `text` should be the FD body as plain text or markdown. `check_urls`
    enables HEAD requests against detected URLs (best-effort, swallows
    network errors as warnings).
    """
    if current_year is None:
        current_year = _dt.date.today().year

    blocks = _find_bibliography_blocks(text)
    entries: list[BibliographyEntry] = []
    issues: list[BibliographyIssue] = []
    fresh = stale = undated = 0

    url_status: dict[str, str] = {}
    if check_urls:
        url_status = _probe_urls_in_text(text, timeout=url_timeout_seconds)

    for s_idx, block in enumerate(blocks):
        for e_idx, raw in enumerate(_split_entries(block)):
            year = _latest_year(raw)
            urls = _extract_urls(raw)
            age = (current_year - year) if year is not None else None
            entry_issues: list[str] = []

            if year is None:
                undated += 1
                entry_issues.append("no_year")
                issues.append(BibliographyIssue(
                    severity="warning",
                    code="bibliography_no_year",
                    message="Intrarea nu conține un an detectabil.",
                    section_index=s_idx,
                    entry_index=e_idx,
                    entry_text=raw,
                ))
            elif age is not None and age > max_age_years:
                stale += 1
                entry_issues.append("stale")
                issues.append(BibliographyIssue(
                    severity="warning",
                    code="bibliography_stale",
                    message=(
                        f"Intrare bibliografică veche de {age} ani "
                        f"(an {year}); recomandat ≤ {max_age_years} ani."
                    ),
                    section_index=s_idx,
                    entry_index=e_idx,
                    entry_text=raw,
                ))
            else:
                fresh += 1

            for url in urls:
                status = url_status.get(url)
                if status and status != "ok":
                    entry_issues.append(f"url:{status}")
                    issues.append(BibliographyIssue(
                        severity="warning",
                        code="bibliography_broken_url",
                        message=f"URL inaccesibil ({status}): {url}",
                        section_index=s_idx,
                        entry_index=e_idx,
                        entry_text=raw,
                    ))

            entries.append(BibliographyEntry(
                section_index=s_idx,
                entry_index=e_idx,
                text=raw,
                latest_year=year,
                urls=urls,
                age_years=age,
                issues=entry_issues,
            ))

    total = len(entries)
    if total == 0:
        summary = "Nu s-au găsit secțiuni Bibliografie în document."
    else:
        summary = (
            f"{total} intrări analizate: {fresh} actuale, {stale} expirate "
            f"(>{max_age_years} ani), {undated} fără an."
        )

    return BibliographyReport(
        entries=entries,
        issues=issues,
        total_entries=total,
        fresh_entries=fresh,
        stale_entries=stale,
        undated_entries=undated,
        summary=summary,
    )


def check_fd_bibliography(
    fd: ExtractedDocument,
    *,
    current_year: int | None = None,
    max_age_years: int = 5,
    check_urls: bool = False,
    url_timeout_seconds: float = 5.0,
) -> BibliographyReport:
    """Variant that pulls bibliography entries directly from a parsed FD.

    Looks at any list-valued field whose key starts with `bibliografie`
    and any table whose name starts with `bibliografie`. Falls back to the
    document `summary` text if no structured entries are found.
    """
    blocks: list[list[str]] = []

    for f in fd.fields:
        if not f.key.lower().startswith("bibliografie"):
            continue
        if isinstance(f.value, list):
            blocks.append([str(v) for v in f.value if str(v).strip()])
        elif isinstance(f.value, str) and f.value.strip():
            blocks.append([f.value.strip()])

    for t in fd.tables:
        if not t.name.lower().startswith("bibliografie"):
            continue
        rows: list[str] = []
        for row in t.rows:
            # Use the longest cell as the entry text (skips index columns).
            if not row:
                continue
            entry = max((c for c in row if isinstance(c, str)), key=len, default="")
            entry = entry.strip()
            if entry:
                rows.append(entry)
        if rows:
            blocks.append(rows)

    if not blocks:
        # Fall back to scanning the summary as plain text.
        return check_bibliography(
            fd.summary or "",
            current_year=current_year,
            max_age_years=max_age_years,
            check_urls=check_urls,
            url_timeout_seconds=url_timeout_seconds,
        )

    if current_year is None:
        current_year = _dt.date.today().year

    entries: list[BibliographyEntry] = []
    issues: list[BibliographyIssue] = []
    fresh = stale = undated = 0

    url_status: dict[str, str] = {}
    if check_urls:
        joined = "\n".join(e for block in blocks for e in block)
        url_status = _probe_urls_in_text(joined, timeout=url_timeout_seconds)

    for s_idx, block in enumerate(blocks):
        for e_idx, raw in enumerate(block):
            year = _latest_year(raw)
            urls = _extract_urls(raw)
            age = (current_year - year) if year is not None else None
            entry_issues: list[str] = []

            if year is None:
                undated += 1
                entry_issues.append("no_year")
                issues.append(BibliographyIssue(
                    severity="warning",
                    code="bibliography_no_year",
                    message="Intrarea nu conține un an detectabil.",
                    section_index=s_idx,
                    entry_index=e_idx,
                    entry_text=raw,
                ))
            elif age is not None and age > max_age_years:
                stale += 1
                entry_issues.append("stale")
                issues.append(BibliographyIssue(
                    severity="warning",
                    code="bibliography_stale",
                    message=(
                        f"Intrare bibliografică veche de {age} ani "
                        f"(an {year}); recomandat ≤ {max_age_years} ani."
                    ),
                    section_index=s_idx,
                    entry_index=e_idx,
                    entry_text=raw,
                ))
            else:
                fresh += 1

            for url in urls:
                status = url_status.get(url)
                if status and status != "ok":
                    entry_issues.append(f"url:{status}")
                    issues.append(BibliographyIssue(
                        severity="warning",
                        code="bibliography_broken_url",
                        message=f"URL inaccesibil ({status}): {url}",
                        section_index=s_idx,
                        entry_index=e_idx,
                        entry_text=raw,
                    ))

            entries.append(BibliographyEntry(
                section_index=s_idx,
                entry_index=e_idx,
                text=raw,
                latest_year=year,
                urls=urls,
                age_years=age,
                issues=entry_issues,
            ))

    total = len(entries)
    summary = (
        f"{total} intrări analizate: {fresh} actuale, {stale} expirate "
        f"(>{max_age_years} ani), {undated} fără an."
    )
    return BibliographyReport(
        entries=entries,
        issues=issues,
        total_entries=total,
        fresh_entries=fresh,
        stale_entries=stale,
        undated_entries=undated,
        summary=summary,
    )


def _probe_urls_in_text(text: str, *, timeout: float) -> dict[str, str]:
    """HEAD-probe every URL found in `text`. Returns mapping url -> status."""
    urls = {m.group(0).rstrip(".,;") for m in _URL_RE.finditer(text)}
    if not urls:
        return {}
    try:
        import httpx
    except ImportError:
        return {u: "unavailable" for u in urls}

    statuses: dict[str, str] = {}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = client.head(url)
                if resp.status_code >= 400:
                    # Some servers reject HEAD; retry GET.
                    resp = client.get(url)
                if 200 <= resp.status_code < 400:
                    statuses[url] = "ok"
                else:
                    statuses[url] = f"http_{resp.status_code}"
            except Exception as exc:  # noqa: BLE001 — network is best-effort
                statuses[url] = f"error:{type(exc).__name__}"
    return statuses
