"""Work out each country's role in each chain, instead of assuming it.

The first version of the concentration analysis hardcoded China as the processing
stage. That produced a clean result for cobalt and rare earths and an inverted one for
lithium hydroxide, because for that commodity China is the producer, not the importer of
feedstock. The assumption was doing work the data should do.

So the role is derived per country per commodity, from how material moves through it:

    throughput ratio = exports / (exports + imports)

    ~1.0  material leaves and little arrives          -> SOURCE
    ~0.5  comparable volumes both ways                -> PROCESSOR (or transit)
    ~0.0  material arrives and little leaves          -> SINK

A source holds the deposit or the primary output. A processor buys one form and sells
another, which is where value is added and where chokepoints tend to sit. A sink consumes.

This is a description of flows, not of intent: a genuine refiner and a pure entrepot port
both show a middling ratio, and telling them apart needs the re-export flags from build.py.
The distinction that matters for supply risk is that both stand between a sink and its
material.
"""
from __future__ import annotations
import pandas as pd

SOURCE, PROCESSOR, SINK = "source", "processor", "sink"
SOURCE_CUT, SINK_CUT = 0.70, 0.30


def throughput(edges_all_flows: pd.DataFrame) -> pd.DataFrame:
    """Per reporter and commodity: imports, exports, ratio, role.

    Only reporters can be classified, because only they report both directions.
    """
    df = edges_all_flows[~edges_all_flows.partner_is_group]
    piv = (df.groupby(["reporter", "reporter_name", "commodity", "flow"])
             .value_usd.sum().unstack("flow").fillna(0.0).reset_index())
    for c in ("M", "X"):
        if c not in piv:
            piv[c] = 0.0
    piv = piv.rename(columns={"M": "imports_usd", "X": "exports_usd"})

    total = piv.imports_usd + piv.exports_usd
    piv["ratio"] = (piv.exports_usd / total).where(total > 0)
    piv["role"] = pd.cut(piv.ratio, [-0.01, SINK_CUT, SOURCE_CUT, 1.01],
                         labels=[SINK, PROCESSOR, SOURCE]).astype("object")
    piv.loc[piv.ratio.isna(), "role"] = None
    return piv.sort_values(["commodity", "exports_usd"], ascending=[True, False])


def role_lookup(tp: pd.DataFrame) -> dict[tuple[int, str], str]:
    return {(int(r.reporter), r.commodity): r.role
            for r in tp.itertuples() if r.role is not None}


if __name__ == "__main__":
    import warnings, pathlib
    warnings.filterwarnings("ignore")
    from build import load_edges
    from fetch import COMMODITIES

    tp = throughput(load_edges())
    have_both = tp[(tp.imports_usd > 0) & (tp.exports_usd > 0)]
    print(f"classified {len(tp):,} country-commodity pairs "
          f"({len(have_both):,} with trade in both directions)\n")

    print("role counts per commodity:")
    print(tp.pivot_table(index="commodity", columns="role", values="reporter",
                         aggfunc="count", fill_value=0).to_string())

    for cmd in sorted(tp.commodity.unique()):
        sub = tp[(tp.commodity == cmd) & tp.role.notna()].nlargest(6, "exports_usd")
        print(f"\n{cmd}  {COMMODITIES[cmd]}")
        for r in sub.itertuples():
            print(f"   {r.reporter_name:<22} in ${r.imports_usd/1e9:>6.2f}bn  "
                  f"out ${r.exports_usd/1e9:>6.2f}bn  ratio {r.ratio:>4.2f}  {r.role}")

    out = pathlib.Path(__file__).resolve().parents[1] / "data" / "processed"
    out.mkdir(parents=True, exist_ok=True)
    tp.to_csv(out / "country_roles.csv", index=False)
    print(f"\nwritten to {out/'country_roles.csv'}")
