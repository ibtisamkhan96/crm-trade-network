"""Assemble the cached Comtrade responses into one bilateral edge table.

Three things get decided here, and each of them changes the answer.

AGGREGATE PARTNERS. Comtrade mixes real countries with aggregate areas in the same
partner field: "World" (code 0), "Other Asia, nes", "Areas, nes", EU groupings. Summing
without dropping these double counts, sometimes by a factor of two. Membership is taken
from the API's own reference table rather than guessed from names.

RE-EXPORT HUBS. The Netherlands, Belgium, Singapore and Hong Kong appear as major
suppliers of materials they hold no deposits of, because Rotterdam and Singapore are
ports. Left alone they dominate any centrality measure and the analysis becomes a map
of shipping rather than of supply risk. They are flagged here, not silently dropped:
whether transit counts as dependency is a judgement the analysis should make explicitly.

VALUE AND WEIGHT BOTH. An HS code spans a range of products, so a country shipping
separated high-purity oxide and one shipping bulk concentrate can look alike by tonnage
and nothing alike by value. Where the two disagree, that disagreement is the signal.
"""
from __future__ import annotations
import json, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"

# Major entrepot economies. Trade recorded against these is frequently transit rather
# than origin. Flagged so downstream analysis can include or exclude them on purpose.
REEXPORT_HUBS = {528: "Netherlands", 56: "Belgium", 702: "Singapore",
                 344: "China, Hong Kong SAR", 784: "United Arab Emirates"}


def _reference() -> tuple[dict[int, str], set[int]]:
    P = json.loads((ROOT / "data" / "partners.json").read_text(encoding="utf-8"))["results"]
    names = {p["PartnerCode"]: p["PartnerDesc"] for p in P}
    groups = {p["PartnerCode"] for p in P if p.get("isGroup")}
    groups.add(0)                                   # "World" is an aggregate too
    return names, groups


def load_edges(year: int = 2023) -> pd.DataFrame:
    """One row per (reporter, partner, commodity, flow), aggregate areas removed."""
    names, groups = _reference()
    rows = []
    for f in sorted(CACHE.glob(f"{year}_*.json")):
        _, cmd, flow, reporter = f.stem.split("_")
        for r in json.loads(f.read_text(encoding="utf-8")):
            rows.append({
                "commodity": cmd, "flow": flow,
                "reporter": int(reporter), "partner": r["partnerCode"],
                "value_usd": r.get("primaryValue") or 0.0,
                "net_kg": r.get("netWgt") or 0.0,
            })
    df = pd.DataFrame(rows)

    df["is_world"] = df.partner == 0
    df["partner_is_group"] = df.partner.isin(groups)
    df["reporter_name"] = df.reporter.map(names)
    df["partner_name"] = df.partner.map(names)
    df["partner_is_hub"] = df.partner.isin(REEXPORT_HUBS)
    df["reporter_is_hub"] = df.reporter.isin(REEXPORT_HUBS)

    # Collapse any duplicate rows the API returns for the same pair.
    keys = ["commodity", "flow", "reporter", "partner", "reporter_name", "partner_name",
            "is_world", "partner_is_group", "partner_is_hub", "reporter_is_hub"]
    return df.groupby(keys, as_index=False, dropna=False)[["value_usd", "net_kg"]].sum()


def bilateral(df: pd.DataFrame, flow: str = "M") -> pd.DataFrame:
    """Real country-to-country edges only: no World, no aggregate regions."""
    return df[(df.flow == flow) & ~df.partner_is_group].copy()



def unified_edges(df: pd.DataFrame) -> pd.DataFrame:
    """One edge list from both reporting directions.

    An import row says "reporter bought from partner"; an export row says "reporter
    sold to partner". Both describe the same directed link, so both are folded into a
    single exporter -> importer table.

    This is not cosmetic. Built from imports alone, only the 30 reporting countries can
    have an incoming edge, and betweenness centrality on that graph largely re-ranks the
    reporter list rather than describing the trade system. Adding the export side gives
    the ~160 partner countries incoming edges too.

    Where both sides report the same link they disagree (see mirror.py, median 23%), so
    the larger of the two is taken. Taking the mean would blend a figure that is often
    right with one that is often missing; the maximum at least reflects trade that one
    party positively recorded.
    """
    d = df[~df.partner_is_group].copy()
    imp = d[d.flow == "M"].rename(columns={"reporter_name": "importer", "partner_name": "exporter"})
    exp = d[d.flow == "X"].rename(columns={"reporter_name": "exporter", "partner_name": "importer"})
    both = pd.concat([imp[["commodity", "exporter", "importer", "value_usd", "net_kg"]],
                      exp[["commodity", "exporter", "importer", "value_usd", "net_kg"]]])
    both = both.dropna(subset=["exporter", "importer"])
    both = both[both.exporter != both.importer]
    return (both.groupby(["commodity", "exporter", "importer"], as_index=False)
                [["value_usd", "net_kg"]].max())


if __name__ == "__main__":
    df = load_edges()
    b = bilateral(df)
    print(f"raw rows           : {len(df):,}")
    print(f"aggregate partners : {int(df.partner_is_group.sum()):,} rows dropped "
          f"(${df.loc[df.partner_is_group, 'value_usd'].sum()/1e9:,.1f}bn, "
          f"which is what double counting would have added)")
    print(f"bilateral edges    : {len(b):,}  across {b.commodity.nunique()} commodities")
    print(f"reporters          : {b.reporter.nunique()}   partners: {b.partner.nunique()}")
    print(f"total import value : ${b.value_usd.sum()/1e9:,.1f}bn")
    print(f"via re-export hubs : ${b.loc[b.partner_is_hub, 'value_usd'].sum()/1e9:,.1f}bn "
          f"({b.loc[b.partner_is_hub, 'value_usd'].sum()/b.value_usd.sum():.1%} of the total)")

    print("\nvalue by commodity ($bn, imports):")
    t = (b.groupby("commodity")
           .agg(edges=("value_usd", "size"), usd_bn=("value_usd", lambda s: s.sum()/1e9),
                kt=("net_kg", lambda s: s.sum()/1e6))
           .sort_values("usd_bn", ascending=False))
    print(t.round(2).to_string())

    out = ROOT / "data" / "processed"; out.mkdir(parents=True, exist_ok=True)
    b.to_csv(out / "bilateral_edges.csv", index=False)
    print(f"\nwritten to {out/'bilateral_edges.csv'}")
