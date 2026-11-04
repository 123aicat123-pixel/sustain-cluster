"""Independent arithmetic cross-check for SustainCluster simulator step reporting.

Checks the simulator's own documented accounting identities. It does NOT
validate PUE, electricity tariffs, lifecycle emissions, or physical realism.
"""
import math


def validate_datacenter_step(dc_info, *, relative_tolerance=1e-8):
    common = dc_info["__common__"]
    battery = dc_info["agent_bat"]
    energy = float(common["energy_consumption_kwh"])
    facility_cost = float(common["energy_cost_USD"])
    carbon = float(common["carbon_emissions_kg"])
    price_per_mwh = float(common["price_USD_kwh"])
    avg_ci_g_per_kwh = float(battery.get("bat_avg_CI", 0))
    values = (energy, facility_cost, carbon, price_per_mwh, avg_ci_g_per_kwh)
    if any((not math.isfinite(x) or x < 0) for x in values):
        raise AssertionError("negative or nonfinite facility accounting value")
    # Original simulator multiplies price_i / 1000, so this field is
    # effectively treated as USD/MWh despite its misleading name.
    expected_cost = energy * price_per_mwh / 1000.0
    expected_carbon = energy * avg_ci_g_per_kwh / 1000.0
    for measured, expected, label in (
        (facility_cost, expected_cost, "cost"),
        (carbon, expected_carbon, "carbon"),
    ):
        if not math.isclose(measured, expected, rel_tol=relative_tolerance, abs_tol=1e-7):
            raise AssertionError(f"facility {label} calculation mismatch: {measured} vs {expected}")
    return {
        "energy_kwh": energy,
        "facility_cost_usd": facility_cost,
        "facility_carbon_kg": carbon,
    }
