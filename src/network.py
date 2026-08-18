"""The trade network: who sits in the middle, and what breaks when they stop.

Concentration measures how spread a country's suppliers are. It cannot see position.
A country can source from ten suppliers and still be exposed, if those ten all draw
from the same place. That is a property of the network, not of any one trade relation,
and it needs the graph to see it.

Two things are computed here.

CHOKEPOINTS. Betweenness centrality on the directed trade graph: how often a country
lies on the path between others. Edge weights are trade value, and betweenness needs a
distance, so weights are inverted before the shortest-path search. A large trader is not
automatically a chokepoint; a chokepoint is a country other countries have to go
through.

CASCADING FAILURE. Remove one exporter and ask how much of everyone else's supply goes
unserved. The answer depends entirely on whether anyone else can expand, so that is made
an explicit parameter rather than an assumption buried in the result: remaining suppliers
can lift output by SLACK of their current exports, and whatever cannot be covered is the
shortfall. SLACK=0 is the pessimistic bound with no substitution at all; SLACK=0.2 allows
a fifth more from everyone still standing. Both are reported, because the gap between
them is the value of having alternatives.

Note what this model does not do. It does not know about long-term substitution, stock
drawdown, price response, or the fact that opening a mine takes a decade. It is a
short-run supply-disruption bound, and should be read as one.
"""
from __future__ import annotations
import pandas as pd
import networkx as nx

from build import load_edges, bilateral, unified_edges
from fetch import COMMODITIES


def build_graph(edges: pd.DataFrame, commodity: str | None = None) -> nx.DiGraph:
    """Directed graph, exporter -> importer, weighted by trade value.

    Rows are importer-reported, so the partner is the source and the reporter is
    the destination. The edge points the way the material moves.
    """
    df = edges if commodity is None else edges[edges.commodity == commodity]
    df = df[df.value_usd > 0]
    agg = df.groupby(["exporter", "importer"], as_index=False).value_usd.sum()

    G = nx.DiGraph()
    for _, r in agg.iterrows():
        G.add_edge(r.exporter, r.importer, value=float(r.value_usd),
                   distance=1.0 / float(r.value_usd))     # cheap to traverse a big flow
    return G


def chokepoints(G: nx.DiGraph, top: int = 12) -> pd.DataFrame:
    """Countries that sit between others, ranked."""
    btw = nx.betweenness_centrality(G, weight="distance", normalized=True)
    out_s = {n: sum(d["value"] for _, _, d in G.out_edges(n, data=True)) for n in G}
    in_s = {n: sum(d["value"] for _, _, d in G.in_edges(n, data=True)) for n in G}
    df = pd.DataFrame({
        "betweenness": pd.Series(btw),
        "exports_usd": pd.Series(out_s),
        "imports_usd": pd.Series(in_s),
    })
    df["out_degree"] = pd.Series(dict(G.out_degree()))
    return df.sort_values("betweenness", ascending=False).head(top)


def cascade(edges: pd.DataFrame, remove: str, slack: float = 0.0) -> dict:
    """Remove one exporter. How much import demand cannot be met?

    Per commodity: the removed country's deliveries are lost. Remaining suppliers
    can collectively add `slack` times their current exports of that commodity.
    Whatever the survivors cannot cover is the shortfall.
    """
    total_lost = total_short = 0.0
    per_commodity = {}
    for cmd, grp in edges.groupby("commodity"):
        lost = grp.loc[grp.exporter == remove, "value_usd"].sum()
        if lost <= 0:
            continue
        survivors = grp.loc[grp.exporter != remove, "value_usd"].sum()
        spare = survivors * slack
        short = max(0.0, lost - spare)
        per_commodity[cmd] = {"lost_usd": lost, "shortfall_usd": short,
                              "share_of_trade": lost / grp.value_usd.sum()}
        total_lost += lost
        total_short += short
    return {"country": remove, "lost_usd": total_lost, "shortfall_usd": total_short,
            "per_commodity": per_commodity}


def rank_by_damage(edges: pd.DataFrame, slack: float = 0.0, top: int = 12) -> pd.DataFrame:
    suppliers = edges.groupby("exporter").value_usd.sum().nlargest(40).index
    rows = []
    for c in suppliers:
        r = cascade(edges, c, slack)
        worst = max(r["per_commodity"].items(), key=lambda kv: kv[1]["share_of_trade"],
                    default=(None, {"share_of_trade": 0}))
        rows.append({"country": c, "lost_usd_bn": r["lost_usd"] / 1e9,
                     "shortfall_usd_bn": r["shortfall_usd"] / 1e9,
                     "commodities_hit": len(r["per_commodity"]),
                     "worst_commodity": worst[0],
                     "worst_share": worst[1]["share_of_trade"]})
    return pd.DataFrame(rows).sort_values("shortfall_usd_bn", ascending=False).head(top)


if __name__ == "__main__":
    import pathlib
    edges = unified_edges(load_edges())

    G = build_graph(edges)
    print(f"network: {G.number_of_nodes()} countries, {G.number_of_edges()} trade links\n")
    print("=== chokepoints: countries other countries trade through ===")
    print(chokepoints(G).assign(
        exports_usd=lambda d: (d.exports_usd / 1e9).round(2),
        imports_usd=lambda d: (d.imports_usd / 1e9).round(2)).round(4).to_string())

    print("\n=== single-supplier removal, ranked by unmet demand ===")
    print("no substitution possible (slack = 0):")
    print(rank_by_damage(edges, slack=0.0).round(3).to_string(index=False))

    print("\nsurvivors can expand 20% (slack = 0.2):")
    print(rank_by_damage(edges, slack=0.2).round(3).to_string(index=False))

    print("\n=== per-commodity chokepoints (betweenness within each chain) ===")
    for cmd in sorted(edges.commodity.unique()):
        g = build_graph(edges, cmd)
        if g.number_of_nodes() < 5:
            continue
        cp = chokepoints(g, top=3)
        names = ", ".join(f"{i} ({v:.3f})" for i, v in cp.betweenness.items())
        print(f"  {cmd} {COMMODITIES[cmd][:38]:<40} {names}")

    out = pathlib.Path(__file__).resolve().parents[1] / "data" / "processed"
    chokepoints(G, top=50).to_csv(out / "chokepoints.csv")
    rank_by_damage(edges, 0.0, top=40).to_csv(out / "cascade_no_substitution.csv", index=False)
    print(f"\nwritten to {out}")
