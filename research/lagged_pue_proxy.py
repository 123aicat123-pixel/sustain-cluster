"""Read-only, one-step-lagged facility-PUE scoring multiplier.

Average PUE is NOT marginal power or counterfactual emissions. This is a
pre-registered routing heuristic ablation, not a physical carbon estimator.
"""


import math


def observed_pue(it_power_kw, hvac_power_kw):
    """Return clipped site PUE, or conservative 1.0 on absent/zero IT."""
    if it_power_kw is None or hvac_power_kw is None:
        return 1.0, True
    it, hvac = float(it_power_kw), float(hvac_power_kw)
    if not math.isfinite(it) or not math.isfinite(hvac) or it < 0 or hvac < 0:
        raise ValueError("invalid nonnegative IT/HVAC telemetry")
    if it <= 1e-9:
        return 1.0, True
    return min(3.0, max(1.0, 1.0 + hvac / it)), False


def observed_facility_multipliers(info_by_name, datacenters):
    """Consume last step's reported values and map site names to DC IDs."""
    if set(info_by_name) != set(datacenters):
        raise AssertionError("missing/extra facility sites in lagged telemetry")
    multipliers = {}
    fallbacks = 0
    for name, dc in datacenters.items():
        agent = info_by_name[name]["agent_dc"]
        multiplier, fallback = observed_pue(
            agent.get("dc_ITE_total_power_kW"),
            agent.get("dc_HVAC_total_power_kW"),
        )
        if dc.dc_id in multipliers:
            raise AssertionError("duplicate data-center ID")
        multipliers[dc.dc_id] = multiplier
        fallbacks += int(fallback)
    return multipliers, fallbacks
