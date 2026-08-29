"""Shared tool plumbing: outcome type, source builders, severity mappings.

Severity thresholds are fixed and documented here per tool. They map deviation
MAGNITUDE to salience — they are not verdicts, not risk scores, and the word
they never reach for is the one the project forbids tools from saying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from interpretex_contracts import Dimension, Observation, SourceRef, Severity, SourceKind


@dataclass
class ToolOutcome:
    ok: bool = True
    summary: str = ""
    observations: list[Observation] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    sources: list[SourceRef] = field(default_factory=list)
    error: Optional[str] = None


def clip(text: str, limit: int = 200) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ------------------------------------------------------------ source builders


def doc_source(doc_id: str, field_name: str, value: Any = None) -> SourceRef:
    return SourceRef(kind=SourceKind.document, ref=f"{doc_id}.{field_name}", value=value,
                     label=doc_id)


def ref_source(table: str, key: str, value: Any = None, as_of: str | None = None,
               label: str | None = None) -> SourceRef:
    ref = f"{table}/{key}" + (f"/{as_of}" if as_of else "")
    return SourceRef(kind=SourceKind.reference_db, ref=ref, value=value, as_of=as_of,
                     label=label or f"{table}/{key}")


def derived_source(tool: str, metric: str, value: Any = None) -> SourceRef:
    return SourceRef(kind=SourceKind.derived, ref=f"{tool}:{metric}", value=value,
                     label=f"{tool}.{metric}")


# --------------------------------------------------------- severity mappings


def price_deviation_severity(outside_band_pct: float) -> Severity:
    """|deviation| beyond the plausible band: <=10% low, <=25% medium, else high.

    Within the band -> none (and then no observation is emitted at all).
    """
    if outside_band_pct <= 0.0:
        return Severity.none
    if outside_band_pct <= 10.0:
        return Severity.low
    if outside_band_pct <= 25.0:
        return Severity.medium
    return Severity.high


def capacity_severity(utilisation_pct: float) -> Severity:
    """<=100% none; <=105% low; <=120% medium; above 120% high."""
    if utilisation_pct <= 100.0:
        return Severity.none
    if utilisation_pct <= 105.0:
        return Severity.low
    if utilisation_pct <= 120.0:
        return Severity.medium
    return Severity.high


def transit_severity(claimed_days: float, band_low: int, band_high: int) -> Severity:
    """Outside the band: how far, as a ratio to the nearest edge.

    ratio <=1.15 low, <=1.5 medium, else high; inside the band -> none.
    """
    if band_low <= claimed_days <= band_high:
        return Severity.none
    if claimed_days < band_low:
        ratio = band_low / max(claimed_days, 1e-9)
    else:
        ratio = claimed_days / max(band_high, 1e-9)
    if ratio <= 1.15:
        return Severity.low
    if ratio <= 1.5:
        return Severity.medium
    return Severity.high


def zscore_severity(abs_z: float) -> Severity:
    """Behavioural price deviation: >=4 high, >=2.5 medium, >=1.5 low, else none."""
    if abs_z >= 4.0:
        return Severity.high
    if abs_z >= 2.5:
        return Severity.medium
    if abs_z >= 1.5:
        return Severity.low
    return Severity.none


def normalise_text(value: Any) -> str:
    return " ".join(str(value).strip().lower().split())


def same_text(a: Any, b: Any) -> bool:
    """Plural- and case-insensitive text comparison.

    "Copper Cathode" vs "copper cathodes" is not a difference;
    "Copper Cathodes" vs "Copper Scrap" is.
    """
    na, nb = normalise_text(a), normalise_text(b)
    if na == nb:
        return True
    strip_s = lambda w: w[:-1] if len(w) > 3 and w.endswith("s") else w  # noqa: E731
    return " ".join(map(strip_s, na.split())) == " ".join(map(strip_s, nb.split()))


def same_number(a: Any, b: Any) -> bool:
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return False
    denom = max(abs(fa), abs(fb), 1.0)
    return abs(fa - fb) / denom <= 0.005
