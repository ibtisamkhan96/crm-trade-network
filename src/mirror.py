"""Do the two sides of a trade agree about what crossed the border?

Every bilateral flow is reported twice. Germany records what it imported from China;
China records what it exported to Germany. One physical shipment, two independent
statistics, and they routinely disagree. Trade economists call the comparison mirror
statistics, and the gap is used as an indicator of misreporting, smuggling, transfer
pricing, and transit misattribution.

One thing has to be handled before any gap means anything. Imports are conventionally
valued CIF, including freight and insurance to the destination, and exports FOB, at the
exporter's border. So the importer's figure should exceed the exporter's by the cost of
carriage even when both are perfectly accurate, typically of order five to ten per cent.
Treating that as error would manufacture a discrepancy in every single pair.

What is reported here is therefore the gap relative to that expectation, so a pair sitting
at the normal freight margin scores near zero and only genuine divergence stands out.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

CIF_FOB_MARGIN = 0.075          # expected import-over-export premium from freight and insurance


def mirror_pairs(edges: pd.DataFrame, min_usd: float = 1e6) -> pd.DataFrame:
    """Match each importer-reported flow to the exporter's account of the same flow."""
    df = edges[~edges.partner_is_group]

    imp = (df[df.flow == "M"]
           .groupby(["commodity", "reporter", "partner"], as_index=False)
           .agg(importer_says=("value_usd", "sum"), importer_kg=("net_kg", "sum"))
           .rename(columns={"reporter": "importer", "partner": "exporter"}))

    exp = (df[df.flow == "X"]
           .groupby(["commodity", "reporter", "partner"], as_index=False)
           .agg(exporter_says=("value_usd", "sum"), exporter_kg=("net_kg", "sum"))
           .rename(columns={"reporter": "exporter", "partner": "importer"}))

    m = imp.merge(exp, on=["commodity", "importer", "exporter"], how="inner")
    m = m[(m.importer_says >= min_usd) & (m.exporter_says >= min_usd)].copy()

    expected = m.exporter_says * (1 + CIF_FOB_MARGIN)
    m["ratio"] = m.importer_says / m.exporter_says
    m["excess_gap"] = (m.importer_says - expected) / expected      # 0 = exactly as expected
    m["abs_gap"] = m.excess_gap.abs()
    m["usd_discrepancy"] = (m.importer_says - expected).abs()
    return m


def summarise(m: pd.DataFrame, names: dict[int, str]) -> pd.DataFrame:
    out = m.copy()
    out["importer_name"] = out.importer.map(names)
    out["exporter_name"] = out.exporter.map(names)
    return out


if __name__ == "__main__":
    import json, pathlib, warnings
    warnings.filterwarnings("ignore")
    from build import load_edges, ROOT
    from fetch import COMMODITIES

    P = json.loads((ROOT / "data" / "partners.json").read_text(encoding="utf-8"))["results"]
    names = {p["PartnerCode"]: p["PartnerDesc"] for p in P}

    m = summarise(mirror_pairs(load_edges()), names)
    if m.empty:
        raise SystemExit("no matched pairs yet: export fetch still running")

    print(f"matched pairs (both sides report, both >= $1m): {len(m):,}")
    print(f"median importer/exporter ratio : {m.ratio.median():.2f}  "
          f"(1.075 would be pure freight margin)")
    print(f"median |gap| beyond freight    : {m.abs_gap.median():.1%}")
    print(f"pairs disagreeing by >50%      : {(m.abs_gap > 0.5).mean():.1%}")
    print(f"pairs disagreeing by >2x       : {(m.abs_gap > 1.0).mean():.1%}")
    print(f"total absolute discrepancy     : ${m.usd_discrepancy.sum()/1e9:,.1f}bn "
          f"on ${m.importer_says.sum()/1e9:,.1f}bn of matched trade")

    print("\n=== disagreement by commodity ===")
    g = (m.groupby("commodity")
           .agg(pairs=("ratio", "size"), median_gap=("abs_gap", "median"),
                over_50pct=("abs_gap", lambda s: (s > 0.5).mean()),
                usd_bn=("usd_discrepancy", lambda s: s.sum() / 1e9))
           .sort_values("median_gap", ascending=False))
    g.index = [f"{c} {COMMODITIES[c][:32]}" for c in g.index]
    print(g.round(3).to_string())

    print("\n=== largest single discrepancies ===")
    top = m.nlargest(12, "usd_discrepancy")
    for r in top.itertuples():
        print(f"  {r.commodity} {str(r.exporter_name)[:20]:<20} -> {str(r.importer_name)[:20]:<20} "
              f"exporter ${r.exporter_says/1e6:>8,.0f}m  importer ${r.importer_says/1e6:>8,.0f}m  "
              f"ratio {r.ratio:>5.2f}")

    out = ROOT / "data" / "processed"
    m.to_csv(out / "mirror_statistics.csv", index=False)
    print(f"\nwritten to {out/'mirror_statistics.csv'}")
