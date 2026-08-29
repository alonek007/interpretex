"""Reference world: loads and indexes data/*.json into memory.

Everything here is a controlled synthetic prototype world — not market,
maritime or sanctions intelligence. Lookup failures are data, not exceptions:
callers (tools) turn a missing key into an observation.
"""

from __future__ import annotations

import json
import math
import os
from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

# ------------------------------------------------------------ data location --


def find_data_dir() -> Path:
    """Locate the reference-world data directory.

    Order: $INTERPRETEX_DATA_DIR, then any repo root above this file that has
    data/commodities.json.
    """
    env = os.environ.get("INTERPRETEX_DATA_DIR", "")
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "commodities.json").exists():
            return p
        raise FileNotFoundError(
            f"INTERPRETEX_DATA_DIR={env!r} does not contain commodities.json")
    for parent in Path(__file__).resolve().parents:
        cand = parent / "data" / "commodities.json"
        if cand.exists():
            return cand.parent
    raise FileNotFoundError(
        "reference world not found: no data/commodities.json above "
        f"{Path(__file__).resolve()} (set INTERPRETEX_DATA_DIR)")


# ------------------------------------------------------------------- geometry --

_EARTH_RADIUS_NM = 3440.065
#: Realistic steaming band as a fraction of a vessel's maximum speed.
SAIL_FAST_FRACTION = 0.95
SAIL_SLOW_FRACTION = 0.60


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in nautical miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * _EARTH_RADIUS_NM * math.asin(math.sqrt(a))


def transit_band_days(distance_nm: float, max_speed_knots: float) -> tuple[int, int]:
    """Expected transit band in whole days.

    Sailing time at 95% and 60% of maximum speed (realistic fast/slow steaming
    fractions); no separate port-handling allowance is added (it is folded into
    the slow fraction). Documented constants; used identically by the generator
    (to build plausible clean voyages) and by check_transit_plausibility.
    """
    fast = distance_nm / (max_speed_knots * SAIL_FAST_FRACTION * 24.0)
    slow = distance_nm / (max_speed_knots * SAIL_SLOW_FRACTION * 24.0)
    return math.ceil(fast), math.floor(slow) + 1


def implied_speed_knots(distance_nm: float, days: float) -> float:
    """Average speed a voyage implies, in knots (distance_nm / (days*24))."""
    if days <= 0:
        return float("inf")
    return distance_nm / (days * 24.0)


# -------------------------------------------------------------- typed records --


@dataclass(frozen=True)
class Commodity:
    key: str
    display_name: str
    hs_code: str
    alt_hs_code: str
    unit: str
    currency: str
    grades: list[dict[str, Any]]
    default_grade: str
    monthly_benchmarks: dict[str, float]
    plausible_band_pct: float
    volume_tiers: list[dict[str, float]]
    density_t_per_m3: float
    packing_factor: float
    typical_qty_tons: list[float]
    drift_description: str
    routes: list[list[str]]

    def benchmark(self, month: str) -> Optional[float]:
        return self.monthly_benchmarks.get(month)

    def nearest_month(self, iso_date: str) -> str:
        """Month key ('YYYY-MM') of the benchmark month containing iso_date."""
        return iso_date[:7]

    def grade_multiplier(self, grade_name: str | None) -> Optional[float]:
        if not grade_name:
            return None
        for g in self.grades:
            if g["name"] == grade_name:
                return float(g["multiplier"])
        return None

    def tier_for(self, quantity: float) -> Optional[dict[str, float]]:
        """Highest volume tier whose min_qty the quantity meets."""
        best = None
        for t in self.volume_tiers:
            if quantity >= t["min_qty"]:
                best = t if best is None or t["min_qty"] > best["min_qty"] else best
        return best

    def alt_destination(self, declared: str, rng_pick=None) -> Optional[str]:
        """A different destination port seen on this commodity's routes."""
        for route in self.routes:
            if route[1] != declared:
                return route[1]
        return None


@dataclass(frozen=True)
class HistoricalTrade:
    trade_id: str
    date: str
    exporter_id: str
    importer_id: str
    commodity: str
    quantity: float
    unit_price: float
    vessel_name: str
    broker_id: Optional[str]
    origin_port: str
    destination_port: str
    outcome: str
    prior_case_ref: Optional[str] = None


# ---------------------------------------------------------------- the world ----


class ReferenceWorld:
    """In-memory, indexed view over data/*.json. Load once, share everywhere."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or find_data_dir()
        commodities = self._read("commodities.json")["commodities"]
        self.commodities: dict[str, Commodity] = {
            c["key"]: Commodity(**c) for c in commodities
        }
        self.ports: dict[str, dict[str, Any]] = {
            p["port_code"]: p for p in self._read("ports.json")["ports"]
        }
        self.vessels: dict[str, dict[str, Any]] = {
            v["vessel_name"]: v for v in self._read("vessels.json")["vessels"]
        }
        self._vessels_by_lower = {k.lower(): v for k, v in self.vessels.items()}
        self.entities: dict[str, dict[str, Any]] = {
            e["entity_id"]: e for e in self._read("entities.json")["entities"]
        }
        self.trades: list[HistoricalTrade] = [
            HistoricalTrade(**t) for t in self._read("historical_trades.json")["trades"]
        ]
        self.trades.sort(key=lambda t: t.date)
        self.clusters: list[dict[str, Any]] = self._read("networks.json")["clusters"]

    @classmethod
    def default(cls) -> "ReferenceWorld":
        """Load the reference world from the resolved data directory."""
        return cls(find_data_dir())

    def _read(self, name: str) -> dict[str, Any]:
        path = self.data_dir / name
        if not path.exists():
            raise FileNotFoundError(f"reference data missing: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    # -- lookups (return None on miss; tools turn misses into observations) --

    def commodity(self, key: str) -> Optional[Commodity]:
        return self.commodities.get(key)

    def find_commodity(self, name_or_key: str) -> Optional[Commodity]:
        """Match by key, display name, or case-insensitive display name."""
        c = self.commodities.get(name_or_key)
        if c:
            return c
        low = name_or_key.strip().lower()
        for c in self.commodities.values():
            if c.display_name.lower() == low or c.key.lower() == low:
                return c
        return None

    def port(self, code: str) -> Optional[dict[str, Any]]:
        return self.ports.get(code)

    def find_port(self, code_or_name: str) -> Optional[dict[str, Any]]:
        p = self.ports.get(code_or_name)
        if p:
            return p
        low = code_or_name.strip().lower()
        for p in self.ports.values():
            if p["name"].lower() == low:
                return p
        return None

    def vessel(self, name: str) -> Optional[dict[str, Any]]:
        if not name:
            return None
        return self.vessels.get(name) or self._vessels_by_lower.get(name.strip().lower())

    def entity(self, entity_id: str) -> Optional[dict[str, Any]]:
        return self.entities.get(entity_id)

    def entities_with_ubo(self, ubo: str) -> list[str]:
        return [e["entity_id"] for e in self.entities.values()
                if ubo in e.get("ultimate_beneficial_owners", [])]

    # -- historical trades ------------------------------------------------

    def trades_for_entity(self, entity_id: str, commodity: str | None = None,
                          before_or_on: str | None = None,
                          lookback_months: int | None = None) -> list[HistoricalTrade]:
        """Prior trades where the entity was exporter or importer."""
        out = []
        for t in self.trades:
            if entity_id not in (t.exporter_id, t.importer_id):
                continue
            if commodity is not None and t.commodity != commodity:
                continue
            if before_or_on is not None and t.date > before_or_on:
                continue
            if lookback_months is not None and before_or_on is not None:
                y, m = int(before_or_on[:4]), int(before_or_on[5:7])
                cutoff_y, cutoff_m = y, m - lookback_months
                while cutoff_m <= 0:
                    cutoff_m += 12
                    cutoff_y -= 1
                cutoff = f"{cutoff_y:04d}-{cutoff_m:02d}-01"
                if t.date < cutoff:
                    continue
            out.append(t)
        return out

    def trades_for_broker(self, broker_id: str) -> list[HistoricalTrade]:
        return [t for t in self.trades if t.broker_id == broker_id]

    def escalated_trades_for_broker(self, broker_id: str) -> list[HistoricalTrade]:
        return [t for t in self.trades_for_broker(broker_id) if t.outcome == "escalated"]

    # -- clusters ----------------------------------------------------------

    def clusters_for_entity(self, entity_id: str) -> list[dict[str, Any]]:
        return [c for c in self.clusters if entity_id in c["member_entity_ids"]]

    # -- geography ---------------------------------------------------------

    def distance_nm(self, origin_code: str, destination_code: str) -> Optional[float]:
        a, b = self.find_port(origin_code), self.find_port(destination_code)
        if not a or not b:
            return None
        return haversine_nm(a["lat"], a["lon"], b["lat"], b["lon"])

    @staticmethod
    def transit_band(distance_nm: float, max_speed_knots: float) -> tuple[int, int]:
        return transit_band_days(distance_nm, max_speed_knots)


@lru_cache(maxsize=1)
def load_world() -> ReferenceWorld:
    """Process-wide shared reference world."""
    return ReferenceWorld()


def prices_summary(prices: list[float]) -> dict[str, float]:
    """min/median/max/std for a list of prices (std is population)."""
    if not prices:
        return {}
    s = sorted(prices)
    n = len(s)
    median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    mean = sum(s) / n
    var = sum((p - mean) ** 2 for p in s) / n
    return {"min": s[0], "median": median, "max": s[-1], "std": var ** 0.5,
            "mean": mean, "count": float(n)}
