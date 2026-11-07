# Prior-art screening for carbon/SLA/queue-aware cloud scheduling

Initial literature screen performed 2026-11-04. **Not an exhaustive
systematic review**; no claim that this source list proves novelty.

Relevant published or accepted papers with overlapping directions:

1. **Hierarchical SLA-aware multi-objective task scheduling in multi-access
   edge computing using fuzzy-AHP and queue stability modeling**
   (Lin and Wang, Journal of Cloud Computing, 18 Aug 2026;
   https://doi.org/10.1186/s13677-026-00967-6).
   Already combines SLA-driven multi-objective resource assignment,
   queue-stability-aware congestion control and adaptive edge-cloud
   migration. Different edge architecture, but the concept
   queue-aware + SLA-aware + multiobjective is not new.
2. **Carbon-Aware Scheduling in Cloud Computing Operations:
   A Multi-Objective Optimisation Approach**
   (Danach et al., IET Smart Grid, 14 Jan 2026;
   https://doi.org/10.1049/stg2.70056).
   Combines energy price and carbon forecasts, multi-objective
   optimization and rolling-horizon decisions across spatial and
   temporal workload placement.
3. **Carbon-aware federated orchestration in edge-cloud systems:
   A multi-objective optimization framework with dynamic spatio-temporal
   workload management**
   (Sustainable Computing: Informatics and Systems, Sep 2026,
   https://doi.org/10.1016/j.suscom.2026.101398).
   Already considers cost, carbon, SLA, changing workload conditions,
   and adaptive objective weighting; do not claim that this combination
   of objectives is novel by itself.
4. **Adaptive Carbon-Aware Scheduling for Federated Cloud Systems with
   Time-Critical Workloads** (2026 IEEE SAMI,
   https://doi.org/10.1109/SAMI68106.2026.11420783).
   Explores EDF/LST deadline priority, low-carbon selection and
   learning-based adaptation using current/historical observations.
5. **Carbon-aware scheduling and distributionally robust optimization
   for cloud systems: forecasting, battery storage, and adaptive
   ambiguity refinement** (Journal of Cloud Computing, 2026,
   https://doi.org/10.1186/s13677-026-00904-7).
   Tackles geo-distributed job deadlines, renewable/battery state and
   uncertain data; pertinent when designing uncertainty-aware models.

## Implications for the working SustainCluster prototype

- The phrase "queue-aware carbon- and SLA-aware NSGA-II" is a
  **method combination**, not a defensible established original contribution.
- Current experimental evidence shows the queue component is contingent on
  contention regime, is not robust across three seeds, and can raise
  **realized** facility carbon markedly even when proxy-carbon predictions
  look favorable. Treat this identified failure mode, its independent
  bookkeeping and strict queue/lifecycle feasibility checks as the source
  of a *specific, falsifiable research hypothesis*.
- A stronger potential contribution would be an **online calibration
  method for marginal facility emissions under congested queues**, with
  uncertainty or safety bounds and a principled SLA risk term, validated
  against each of the above comparable baselines.
- The project's current workloads are **independent jobs**, not DAG
  workflow graphs. A DAG-scheduling novelty statement needs independent
  dependency-aware modeling and experiments.
- Before submission, perform a broader 2024–2026 prior-art and code
  replication review, evaluate additional real workload dates and load
  regimes, report wall-time and evaluation budgets, and include genuine
  ablations plus confidence intervals over independent scenarios.

This screening is deliberately conservative: it identifies overlaps
rather than implying exact equivalence between different platforms.
