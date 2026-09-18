# Critical raw materials: the trade network, and what it hides

Bilateral trade in eight critical raw material commodities, built into a directed network
to ask three questions: how concentrated is supply, who sits in the middle, and what
breaks when one country stops.

It also contains a finding that went against the hypothesis it was built to test, which
is written up rather than removed.

## Data

**UN Comtrade**, 2023, via the free public API. 528 cached queries: 8 commodity codes ×
33 reporting countries × both directions. 6,372 import rows and 8,457 export rows.

Codes are chosen so each is a distinct point in a supply chain rather than a vague
material group:

| HS | commodity |
|---|---|
| 2504 | Natural graphite |
| 2805 | Rare earth metals, scandium, yttrium |
| 2825 | Metal oxides and hydroxides (incl. lithium hydroxide) |
| 2836 | Carbonates (incl. lithium carbonate) |
| 2846 | Rare earth compounds |
| 7403 | Refined copper |
| 7502 | Unwrought nickel |
| 8105 | Cobalt mattes and articles |

### Three data problems that change the answer

**The 500-row cap.** Comtrade returns rows split by transport mode and customs procedure,
and the public endpoint caps at 500. Ask naively for German rare earth imports and you get
exactly 500 rows: a truncated slice, with nothing to tell you it is truncated. Passing
`motCode=0&customsCode=C00&partner2Code=0` requests pre-aggregated rows and the same query
returns 24 complete records.

**Aggregate partners.** "World", "Other Asia, nes" and EU groupings sit in the same
partner field as real countries. Dropping them removes $131.1bn against a $130.4bn
bilateral total, which is the double count avoided.

**One-directional graphs.** Built from imports alone, only the 33 reporting countries can
have an incoming edge, and betweenness centrality on that graph mostly re-ranks the
reporter list. Folding in the export side takes the network from 162 nodes and 1,852 links
to **225 nodes and 3,671 links**, and China's betweenness from 0.117 to 0.561.

## Findings

### 1. Two governments describing the same shipment disagree by a median of 23%

Every trade flow is reported twice: once by the importer, once by the exporter. Comparing
them is the standard mirror-statistics check.

One correction has to come first. Imports are valued CIF and exports FOB, so the importer's
figure should exceed the exporter's by freight and insurance, roughly 7.5%, even when both
are correct. Scoring the raw difference would manufacture a discrepancy on every pair.

Across **976 matched pairs** where both sides report and both exceed $1m:

| | |
|---|---|
| median gap beyond freight | **23.0%** |
| pairs disagreeing by more than 50% | **27.3%** |
| pairs disagreeing by more than 2× | 8.1% |
| total absolute discrepancy | **$23.6bn** on $80.6bn of matched trade |

Worst by commodity: unwrought nickel (median 33.7%), rare earth metals (32.0%), cobalt
(30.3%).

The largest single case is not obscure:

| flow | exporter says | importer says | ratio |
|---|---|---|---|
| **Chile → China, lithium carbonate** | $2,550m | $5,777m | **2.27** |
| USA → China, rare earth compounds | $319m | $9m | 0.03 |
| Malaysia → China, refined copper | $61m | $840m | 13.85 |

Chile to China in lithium carbonate is among the most closely watched relationships in
critical minerals, and the two governments' figures differ by a factor of 2.3, a $3.2bn gap
on one bilateral flow.

Some of this has innocent causes: transit through third countries, shipments crossing a
year boundary, re-exports attributed differently. It is not evidence of fraud. But any
supply chain model built on trade statistics inherits roughly 23% median uncertainty, and
most published analyses do not carry an error bar of that size.

### 2. Trade size and systemic criticality are different things

Remove one exporter and ask how much import demand cannot be met. The answer depends
entirely on whether anyone else can expand, so that is an explicit parameter rather than a
buried assumption: survivors can lift output by `slack` of their current exports.

| removed | lost, no substitution | shortfall at 20% slack | absorbed |
|---|---|---|---|
| Chile | $28.8bn | $11.9bn | 59% |
| China | $18.7bn | $10.9bn | 42% |
| DR Congo | $12.7bn | $2.0bn | 84% |
| **Myanmar** | **$1.5bn** | **$1.2bn** | **21%** |
| Russia | $7.3bn | $0.0bn | 100% |
| Japan | $8.0bn | $0.0bn | 100% |

Russia, Japan, Canada, the USA, Kazakhstan and Peru each lose billions in trade and produce
**zero** unmet demand: large but replaceable. Myanmar is the smallest name here and the
least substitutable, with 79% of what it supplies uncoverable by anyone else expanding.

No concentration metric produces that ranking. It needs the network plus a stated
substitution assumption.

### 3. The hypothesis this was built to test did not survive

The project started from a specific claim: that concentration is worse one link upstream,
so consumer-side statistics understate dependency.

Splitting importers into China and everyone else, that looked strongly true, 2.1× median
across eight commodities, with cobalt at 11×.

Then the stage assignment was rebuilt to derive each country's role from its own
export/import balance per commodity rather than assuming China is always the processor.
On that basis the effect **disappears**: processors face tighter supply in 4 of 8
commodities, median ratio 0.65×.

The reason is worth more than the original claim. Within HS 8105 China is a net importer,
so the model classifies it as a sink, and correctly: China imports cobalt *mattes* and
exports cobalt *chemicals*, which carry a different HS code. The transformation that makes
China a processor is invisible inside any single code.

**Supply chain position is defined by the transformation, and transformations cross HS
codes.** A stage cannot be derived from one commodity code in isolation. The first version
got a clean answer by assuming the thing it should have measured.

What survives is specific and checkable:

| | |
|---|---|
| China's cobalt matte imports | **97% from DR Congo** |
| China's rare earth compound imports | **66% from Myanmar** |
| China's lithium carbonate imports | **87% from Chile** |

Those are real single-source dependencies, invisible in European or US import statistics
because they sit one link away. What does not hold is the general law built on them.

### 4. The network has a real phase transition, sharp and abrupt, same shape as the published cobalt cascade study

Wu Chen's group (Ouyang et al., *Environ. Sci. Ecotechnol.* 29 (2026) 100654) run a linear-threshold
cascade across six real cobalt life-cycle stages, mining through recycling, to show disruptions
propagate as "abrupt, nonlinear failures." That six-stage breakdown needs trade-linked material flow
data this project does not have. What it does have is one real trade layer, so `shock_propagation.py`
implements the same core mechanism, a country collapses once the disruption it absorbs from already-
collapsed partners exceeds a threshold share (`beta`) of its own trade, then passes disruption on to
its own neighbours, on the real 2023 network already built above.

Sweeping `beta` from a shock at Myanmar or China in rare earth compounds:

| beta | Myanmar | China |
|---|---|---|
| 0.05 - 0.30 | 100% collapse | 100% collapse |
| 0.50 | 37.4% collapse | 37.4% collapse |
| 0.70 | 0% collapse | 16.3% collapse |
| 0.90 | 0% collapse | 5.7% collapse |

The transition from total collapse to near-immunity happens inside a narrow band, not gradually,
the same "robust-yet-fragile" shape the published study reports, even without its six-layer
structure. Below the transition, essentially any shock at either a supply chokepoint (Myanmar) or a
demand/processing hub (China) takes down the entire network; above it, the network absorbs almost
everything.

**Where this honestly diverges from the published result.** Iterating a shock from every country in
turn (the avalanche network) gives 777 links at beta=0.2 against the underlying trade network's 929,
0.8x as dense, not the ~4x denser finding the cobalt paper reports. The likely reason is structural,
not a modelling error: their extra density comes specifically from indirect paths that cross life-
cycle stages, a shock reaching a country through refining that it could never reach through trade
alone. A single trade layer has no such cross-stage route to travel through, so it cannot produce
that same extra density, whatever threshold is chosen. This is a real, checkable limit of using one
layer rather than six, not a discrepancy to explain away.

**Lithium shows the same pattern, and it lines up with Wu Chen's own separate lithium paper, not
just the cobalt one.** Running the identical cascade on lithium carbonate (HS 2836) and lithium
hydroxide (HS 2825) instead of rare earths or cobalt:

| beta | Chile (lithium carbonate) | China (lithium carbonate) |
|---|---|---|
| 0.05 - 0.30 | 100% collapse | 100% collapse |
| 0.50 | 18.5% collapse | 18.5% collapse |
| 0.70 | 0.5% collapse | 7.9% collapse |
| 0.90 | 0.5% collapse | 5.1% collapse |

Chile shocks the network exactly as hard as China does below the transition, in both lithium codes,
not just one, and both collapse the entire 216-country network at beta &le; 0.3. This is the same
"robust-yet-fragile" shape reported for cobalt above, and it is also the same shape her actual 2024
lithium paper (Ouyang, Liu, **Chen W.**, Wang, Sun, He, Liu, *Environ. Sci. Technol.* 58 (2024)
22135-22147) reports for the lithium network specifically: robust to random shocks, fragile to a
targeted one at the right node. The concentration finding from earlier in this README (China's
lithium carbonate imports 87% from Chile) is exactly the single-supplier dependency this cascade
result explains mechanically: Chile is not just concentrated, it is a node whose removal the network
cannot structurally absorb below a fairly high failure threshold.

```
src/shock_propagation.py   the cascade, systemic fragility, and avalanche network
```

## Layout

```
src/fetch.py           cached Comtrade client, rate-limit aware
src/build.py           edge tables; aggregate areas removed, re-export hubs flagged
src/roles.py           source / processor / sink, derived per country per commodity
src/concentration.py   HHI by commodity and by role
src/network.py         betweenness chokepoints and single-supplier cascade
src/mirror.py          importer vs exporter accounts of the same flow
```

## Limitations

- One year, 2023. No trend, and 2023 was not a normal year for lithium prices.
- 33 reporters. Their partners appear, but countries that report nothing are represented
  only through their counterparties.
- The cascade is a short-run bound. It knows nothing about stock drawdown, price response,
  long-term substitution, or the decade it takes to open a mine.
- Betweenness is still distorted by entrepôt trade. Re-export hubs are flagged in
  `build.py` but not removed, because whether transit counts as dependency is a judgement
  the reader should make, not one the code should make silently.
- Value and weight can tell different stories within one HS code, since a code spans a
  range of product purities. Both are carried; the headline figures use value.
