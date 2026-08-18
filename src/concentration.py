"""How concentrated is supply, and where in the chain does the concentration sit.

The standard way to assess critical mineral risk is to take what consuming economies
import and measure how concentrated the sources are. That answers the wrong question by
one link.

These chains have a processing stage in the middle, and for every material here that
stage is dominated by China. So China's own import mix is not consumption, it is
feedstock sourcing, and it belongs to a different point in the chain than Germany's or
Japan's. Pooling them averages two distinct dependencies into one number that describes
neither.

Splitting on that gives the result the project is built around: upstream concentration
runs several times higher than downstream, so the tightest dependency is the one that
consumer-side statistics cannot see.

Concentration is Herfindahl-Hirschman, the sum of squared supplier shares. 1.0 is a
single source, 0.1 is roughly ten equal ones. Competition authorities treat 0.25 as
highly concentrated.
"""
from __future__ import annotations
import pandas as pd

from build import load_edges, bilateral
from fetch import COMMODITIES
from roles import throughput, role_lookup, SINK, PROCESSOR, SOURCE


def hhi(shares: pd.Series) -> float:
    total = shares.sum()
    return float(((shares / total) ** 2).sum()) if total > 0 else float("nan")


def concentration(edges: pd.DataFrame, roles: dict, metric: str = "value_usd") -> pd.DataFrame:
    """Supplier concentration per commodity, split by the importer's role in that chain.

    Roles come from roles.py, derived from each country's own export/import balance,
    rather than assuming which country occupies the processing stage.
    """
    rows = []
    e = edges.copy()
    e["role"] = [roles.get((r, c)) for r, c in zip(e.reporter, e.commodity)]
    for cmd, grp in e.groupby("commodity"):
        for label, sub in (("sinks source from", grp[grp.role == SINK]),
                           ("processors source from", grp[grp.role == PROCESSOR]),
                           ("sources source from", grp[grp.role == SOURCE]),
                           ("Pooled", grp)):
            by_src = sub.groupby("partner_name")[metric].sum()
            by_src = by_src[by_src > 0]
            if by_src.empty:
                continue
            top = by_src.sort_values(ascending=False)
            rows.append({
                "commodity": cmd, "description": COMMODITIES.get(cmd, ""), "stage": label,
                "total_usd_bn": sub[metric].sum() / (1e9 if metric == "value_usd" else 1e6),
                "suppliers": len(by_src), "hhi": hhi(by_src),
                "top1": top.index[0], "top1_share": top.iloc[0] / top.sum(),
                "top3_share": top.head(3).sum() / top.sum(),
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    all_flows = load_edges()
    edges = bilateral(all_flows)
    roles = role_lookup(throughput(all_flows))

    for metric, unit in (("value_usd", "$bn"),):
        c = concentration(edges, roles, metric)
        print(f"\n{'='*92}\nSUPPLIER CONCENTRATION BY {unit}\n{'='*92}")
        for cmd in sorted(c.commodity.unique()):
            sub = c[c.commodity == cmd].set_index("stage")
            print(f"\n{cmd}  {COMMODITIES[cmd]}")
            for stage in ("sinks source from", "processors source from",
                          "sources source from", "Pooled"):
                if stage not in sub.index:
                    continue
                r = sub.loc[stage]
                print(f"   {stage:<14} {unit} {r.total_usd_bn:>8,.2f}  "
                      f"HHI {r.hhi:>5.3f}  top3 {r.top3_share:>5.1%}  "
                      f"| {r.top1} {r.top1_share:.0%}")

    # the headline comparison
    c = concentration(edges, roles, "value_usd").pivot(index="commodity", columns="stage", values="hhi")
    keep = [x for x in ("processors source from", "sinks source from") if x in c]
    if len(keep) == 2:
        c = c.dropna(subset=keep)
        c["ratio"] = c["processors source from"] / c["sinks source from"]
        bar = "=" * 92
        print("\n" + bar + "\nDOES THE PROCESSING STAGE FACE TIGHTER SUPPLY THAN THE CONSUMING STAGE?\n" + bar)
        print(c[keep + ["ratio"]].round(3).to_string())
        print(f"\nprocessors face tighter supply in {int((c.ratio > 1).sum())} of {len(c)} commodities; "
              f"median ratio {c.ratio.median():.2f}x")

    import pathlib
    out = pathlib.Path(__file__).resolve().parents[1] / "data" / "processed"
    concentration(edges, roles, "value_usd").to_csv(out / "concentration.csv", index=False)
    print(f"\nwritten to {out / 'concentration.csv'}")
