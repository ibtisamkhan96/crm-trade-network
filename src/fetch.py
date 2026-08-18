"""Pull bilateral trade in critical raw materials from UN Comtrade.

Two things about this API decide the whole design.

First, rows come disaggregated by mode of transport and customs procedure, and the
free preview endpoint returns at most 500 of them. Ask naively and you get a silently
truncated, biased slice of a large country's trade. Passing motCode=0, customsCode=C00
and partner2Code=0 requests the already-aggregated rows instead: German rare earth
compound imports drop from a truncated 500 to a complete 24.

Second, it rate-limits hard. Requests are therefore serialised with a pause, and every
response is cached to disk so the network is only ever hit once per query. Re-running
this script after an interruption resumes rather than restarting.
"""
from __future__ import annotations
import json, time, pathlib, urllib.parse, urllib.request

BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
CACHE = pathlib.Path(__file__).resolve().parents[1] / "data" / "cache"
PAUSE_SECONDS = 4.0
UA = "Mozilla/5.0 (compatible; crm-trade-network/1.0; research)"

# HS codes chosen so each one is a distinct point in a supply chain rather than a
# vague commodity group. Ores are where geology binds; refined and compound forms are
# where processing concentrates, and processing is usually the tighter chokepoint.
COMMODITIES = {
    "2805": "Rare earth metals, scandium and yttrium",
    "2846": "Rare earth compounds",
    "2836": "Carbonates (incl. lithium carbonate)",
    "2825": "Metal oxides and hydroxides (incl. lithium hydroxide)",
    "8105": "Cobalt mattes and articles",
    "2504": "Natural graphite",
    "7502": "Unwrought nickel",
    "7403": "Refined copper",
}

# Reporters: the large consuming economies plus the significant producers. Comtrade
# uses M49 numeric codes.
REPORTERS = {
    276: "Germany", 842: "USA", 392: "Japan", 410: "Rep. of Korea", 156: "China",
    250: "France", 380: "Italy", 528: "Netherlands", 826: "United Kingdom",
    724: "Spain", 616: "Poland", 56: "Belgium", 40: "Austria", 752: "Sweden",
    246: "Finland", 208: "Denmark", 578: "Norway", 372: "Ireland", 203: "Czechia",
    699: "India", 76: "Brazil", 484: "Mexico", 124: "Canada", 36: "Australia",
    710: "South Africa", 458: "Malaysia", 764: "Thailand", 704: "Viet Nam",
    360: "Indonesia", 702: "Singapore", 792: "Turkiye", 643: "Russia", 152: "Chile",
}

FLOWS = {"M": "import", "X": "export"}


def _cache_path(reporter: int, cmd: str, flow: str, year: int) -> pathlib.Path:
    return CACHE / f"{year}_{cmd}_{flow}_{reporter}.json"


def fetch(reporter: int, cmd: str, flow: str, year: int, retries: int = 3) -> list[dict]:
    """One reporter, one commodity, one direction, all partners. Cached."""
    path = _cache_path(reporter, cmd, flow, year)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    params = {
        "reporterCode": reporter, "period": year, "cmdCode": cmd, "flowCode": flow,
        "motCode": 0,          # all modes of transport, pre-aggregated
        "customsCode": "C00",  # all customs procedures, pre-aggregated
        "partner2Code": 0,     # no second-partner breakdown
    }
    url = f"{BASE}?{urllib.parse.urlencode(params)}"

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                payload = json.loads(r.read().decode("utf-8"))
            rows = payload.get("data") or []
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(rows), encoding="utf-8")
            return rows
        except Exception as exc:
            # 429 is the common one. Back off rather than hammering.
            wait = PAUSE_SECONDS * (attempt + 2) ** 2
            print(f"    retry {attempt+1}/{retries} after {wait:.0f}s ({type(exc).__name__})", flush=True)
            time.sleep(wait)
    print(f"    GAVE UP: reporter={reporter} cmd={cmd} flow={flow}", flush=True)
    return []


def fetch_all(year: int = 2023, flows: tuple[str, ...] = ("M",)) -> int:
    total = 0
    jobs = [(r, c, f) for c in COMMODITIES for f in flows for r in REPORTERS]
    for i, (rep, cmd, flow) in enumerate(jobs, 1):
        cached = _cache_path(rep, cmd, flow, year).exists()
        rows = fetch(rep, cmd, flow, year)
        total += len(rows)
        print(f"[{i:>3}/{len(jobs)}] {REPORTERS[rep]:<16} {cmd} {FLOWS[flow]:<6} "
              f"{len(rows):>4} rows{' (cached)' if cached else ''}", flush=True)
        if not cached:
            time.sleep(PAUSE_SECONDS)
    return total


if __name__ == "__main__":
    n = fetch_all()
    print(f"\ndone: {n:,} rows across {len(list(CACHE.glob('*.json')))} cached queries")
