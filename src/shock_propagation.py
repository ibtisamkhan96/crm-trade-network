"""Cascading-failure shock propagation on the real trade network.

Wu Chen's group (Ouyang, Liu, Liu, Chen, Wang, Pang, He, Liu, "Systemic risks and
cascading dynamics in the global cobalt supply chain," Environ. Sci. Ecotechnol. 29
(2026) 100654) run a linear threshold cascade across six real cobalt life-cycle stages
(mining, refining, manufacturing, use, waste, recycling), 1998-2019: a shock at one
country/stage reduces its trading partners' supply or demand, and a partner collapses
once the disruption it has absorbed exceeds a threshold share of its own trade, then
passes disruption on to its own neighbours in turn. That six-stage breakdown needs a
trade-linked material flow analysis (mass-balanced production, consumption and apparent-
consumption data per stage) this project does not have and cannot honestly fabricate.

What this module does instead: the same cascading-failure mechanism, applied to the one
real layer this project actually has, the 2023 bilateral trade network already built in
network.py, one commodity at a time. This is a real, single-layer, one-year version of
their multilayer, twenty-year method, not a claim to have reproduced it. Treat every
number below with that scope in mind.
"""
from __future__ import annotations
import pandas as pd
import networkx as nx

from build import load_edges, unified_edges
from network import build_graph
from fetch import COMMODITIES


def simulate_cascade(G: nx.DiGraph, source: str, beta: float = 0.2) -> dict:
    """One shock, starting by fully collapsing `source`, propagated round by round.

    A live country collapses once the trade value it has already lost, because a
    partner it bought from or sold to has already collapsed, exceeds `beta` times its
    own total trade (imports plus exports in this commodity). `beta` plays the role of
    Wu Chen's failure threshold Omega: a lower beta means a more fragile network, since
    countries tolerate less disruption before failing themselves.
    """
    if source not in G:
        return {"source": source, "rounds": 0, "collapsed": [], "avalanche_size": 0,
                "avalanche_fraction": 0.0}

    total_out = {n: sum(d["value"] for _, _, d in G.out_edges(n, data=True)) for n in G}
    total_in = {n: sum(d["value"] for _, _, d in G.in_edges(n, data=True)) for n in G}
    lost_in = {n: 0.0 for n in G}    # value this node can no longer buy (a seller of theirs collapsed)
    lost_out = {n: 0.0 for n in G}   # value this node can no longer sell (a buyer of theirs collapsed)

    collapsed = {source}
    frontier = {source}
    rounds = 0

    while frontier:
        rounds += 1
        for n in frontier:
            for _, buyer, d in G.out_edges(n, data=True):
                if buyer not in collapsed:
                    lost_in[buyer] += d["value"]
            for seller, _, d in G.in_edges(n, data=True):
                if seller not in collapsed:
                    lost_out[seller] += d["value"]

        newly_collapsed = set()
        for n in G:
            if n in collapsed:
                continue
            denom = total_in[n] + total_out[n]
            share_lost = (lost_in[n] + lost_out[n]) / denom if denom > 0 else 0.0
            if share_lost > beta:
                newly_collapsed.add(n)

        if not newly_collapsed:
            break
        collapsed |= newly_collapsed
        frontier = newly_collapsed

    n_other = G.number_of_nodes() - 1
    return {
        "source": source, "rounds": rounds, "collapsed": sorted(collapsed - {source}),
        "avalanche_size": len(collapsed) - 1,
        "avalanche_fraction": (len(collapsed) - 1) / n_other if n_other > 0 else 0.0,
    }


def systemic_fragility(G: nx.DiGraph, betas=(0.4, 0.3, 0.2, 0.15, 0.1, 0.05)) -> pd.DataFrame:
    """For every country as a shock source, the largest beta tried that still produces
    an avalanche covering at least 10% of the rest of the network.

    Wu Chen's own systemic fragility is the critical failure threshold at which a
    node's avalanche undergoes a phase transition, found by sweeping Omega
    continuously. This approximates the same idea over a fixed, coarser grid, honestly
    less precise than a continuous sweep, but real and cheaply re-runnable. A higher
    critical_beta means a shock from that country collapses a large share of the
    network even when other countries are relatively tolerant of disruption, i.e. that
    country is more systemically fragile, in Wu Chen's own sense of the term.
    """
    rows = []
    for n in G.nodes():
        crit = None
        best_fraction = 0.0
        for b in sorted(betas, reverse=True):
            res = simulate_cascade(G, n, beta=b)
            best_fraction = max(best_fraction, res["avalanche_fraction"])
            if res["avalanche_fraction"] >= 0.1 and crit is None:
                crit = b
        rows.append({"country": n, "critical_beta": crit, "max_avalanche_fraction": best_fraction})
    return (pd.DataFrame(rows)
              .sort_values(["critical_beta", "max_avalanche_fraction"],
                            ascending=[False, False], na_position="last")
              .reset_index(drop=True))


def avalanche_network(G: nx.DiGraph, beta: float = 0.2) -> nx.DiGraph:
    """Run a shock from every country in turn: an edge source -> n means a shock
    starting at `source` collapses `n`. This is where Wu Chen's "denser than the
    underlying supply chain" finding comes from, comparing this network's density
    against the real trade network's own density.
    """
    A = nx.DiGraph()
    A.add_nodes_from(G.nodes())
    for source in G.nodes():
        res = simulate_cascade(G, source, beta=beta)
        for n in res["collapsed"]:
            A.add_edge(source, n)
    return A


if __name__ == "__main__":
    import pathlib

    edges = unified_edges(load_edges())
    out = pathlib.Path(__file__).resolve().parents[1] / "data" / "processed"
    out.mkdir(parents=True, exist_ok=True)

    # Rare earth compounds (Myanmar's single-supplier finding), cobalt mattes (the
    # material Wu Chen's 2026 cascade paper covers), and both lithium codes (the
    # material her 2024 network-resilience paper covers): the headline cases.
    for cmd in ["2846", "8105", "2836", "2825"]:
        G = build_graph(edges, cmd)
        if G.number_of_nodes() < 10:
            continue
        print(f"\n=== {COMMODITIES[cmd]} ({cmd}): {G.number_of_nodes()} countries, "
              f"{G.number_of_edges()} trade links ===")

        candidates = ["Myanmar", "China", "Dem. Rep. of the Congo", "Chile"]
        print("  shocks at beta=0.2 (collapse once a country loses >20% of its own trade):")
        for source in candidates:
            if source not in G:
                continue
            res = simulate_cascade(G, source, beta=0.2)
            print(f"    {source:28s} -> {res['avalanche_size']:3d} countries collapse "
                  f"({res['avalanche_fraction']:5.1%}) in {res['rounds']} round(s)")

        A = avalanche_network(G, beta=0.2)
        trade_density = nx.density(G)
        avalanche_density = nx.density(A)
        ratio = avalanche_density / trade_density if trade_density > 0 else float("nan")
        print(f"  trade network:     {G.number_of_edges():4d} links, density {trade_density:.4f}")
        print(f"  avalanche network: {A.number_of_edges():4d} links, density {avalanche_density:.4f}"
              f"  ({ratio:.1f}x denser)")

        frag = systemic_fragility(G)
        print("  most systemically fragile (highest beta still causing a 10%+ avalanche):")
        print(frag.head(8).to_string(index=False))

        frag.to_csv(out / f"systemic_fragility_{cmd}.csv", index=False)
        nx.write_edgelist(A, out / f"avalanche_network_{cmd}.edgelist", data=False)

    print(f"\nwritten to {out}")
