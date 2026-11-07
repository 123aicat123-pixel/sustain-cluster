# Carbon proxy mismatch: site-by-site IT/HVAC accounting (2026-11-05)

## Data, provenance and claim boundary

Source: **completed successful** after-step facility telemetry audit, https://github.com/123aicat123-pixel/sustain-cluster/actions/runs/41986849327 , with archived `facility-telemetry-jun15_05` (artifact 13396900939) and `facility-telemetry-nov12_05` (artifact 13396577663). All admitted tasks finished, no fallback; paired seed 901/1701 matched by calendar/admission. Task date 15 June and CPU scale 5%, seed 1701 is the informative changed-decision case. Comparisons are *retrospective simulations*, not novel prospective holdouts.

Facility-cell records contain post-step IT kW, HVAC kW, total DC kW, battery-adjusted grid energy kWh, effective carbon intensity g/kWh, and output kg CO2 for every one of 128 steps × five datacenters × all policies. These values are not exposed to the online routing policies.

Compared `queue_nsga2_front_carbon_taskwise` **minus** `queue_nsga2_with_transit`.

| DC | Region from configured DC mapping | Grid energy Δ kWh | Actual facility carbon Δ kg |
|---|---|---:|---:|
| DC1 | US-CAL-CISO | -2.8293 | -0.7351 |
| DC2 | DE-LU | -27.9401 | -6.2793 |
| DC3 | CL-SIC | +6.8006 | +1.3895 |
| DC4 | SG | +4.4630 | +1.6646 |
| DC5 | AU-NSW | +10.4429 | +6.5100 |
| **Total** | | **-9.0629** | **+2.5497** |

Despite **9.063 kWh less** aggregate grid energy, the scenario's facility carbon **increased 2.550 kg** because energy shifts across site/time cells with different (but within-cell unchanged) effective carbon intensities. DC5 incurred a +6.510 kg carbon shift that outweighed DC2's -6.279 kg; other centers contributed the remaining changes.

Exact retrospective decomposition at each matching (seed, DC, time step) with reference-cell CI:

`ΔC = ΔP_IT × 0.25h × CI_ref / 1000 + ΔP_HVAC × 0.25h × CI_ref / 1000 + [ΔE_grid - ΔP_total × 0.25h] × CI_ref / 1000 + E_grid,candidate × (CI_candidate-CI_ref) / 1000`.

For June 15 seed 1701, summing cells yields:

| Term | Carbon difference (kg) |
|---|---:|
| IT power effect | +1.3273 |
| HVAC / cooling power effect | +1.2224 |
| Residual battery/grid energy adjustment | approximately 0 |
| Within-cell effective CI difference | exactly 0 |
| **Actual facility carbon** | **+2.5497** |

This is a deterministic accounting attribution, not a causal counterfactual explanation. In this run, **effective CI was identical between both policies within each center/time cell**, so increased emissions cannot be blamed on an altered CI signal. The lower-energy/higher-carbon effect comes from where and when the energy usage moved; IT power and HVAC both matter. Facility power components reconcile to total power within numerical tolerance, and energy differences reconcile to 0.25-hour power differences for this case.

**Implications for next algorithm:** current optimizer's `6 W/core × duration × instant CI` surrogate lacks location-specific IT and HVAC marginal power, the queue/timing of energy consumption, facility background energy, and battery effects. Before fitting a new surrogate, use **prior-date** facility telemetry to benchmark forecast error across site, time and load, then freeze all coefficients/selection rules prior to testing on new untouched arrival dates. A naive linear carbon objective or post-hoc carbon selection must not be called real-carbon-safe.

Caveats: 5% scaled CPU capacities and fixed hourly traces are simulator abstractions; 128 time steps include a drain interval with static/background power. The current platform schedules independent jobs, not DAG workflow precedence. Three-objective superiority, scientific novelty and deployment validity remain unproven.

## Implementation status

A standalone `research/facility_power_carbon_attribution.py` computes this four-part reconciliation for any matched per-step telemetry. Unit tests and a GitHub workflow revision have been submitted. **New CI run must pass before the new code is treated as validated; the numerical example above was independently recomputed from the earlier successful telemetry artifact.**
