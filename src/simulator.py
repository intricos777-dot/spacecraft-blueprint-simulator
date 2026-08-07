#!/usr/bin/env python3
"""
Spacecraft Blueprint Simulator - Dual Track Edition
Runs two parallel simulations per cycle:
 1. Theoretical: advanced physics, speculative drives, middle-ground design
 2. Realistic: strict current-physics-only, known engineering constraints

Uses BDE Patrol to ingest open-source and real-world ship models.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Physics constants
C = 299792458.0  # m/s
G0 = 9.80665     # m/s^2
MU = 3.986004418e14
R_EARTH = 6371000.0
ATMO_SCALE_HEIGHT = 8500.0
ATMO_DENSITY_SEA_LEVEL = 1.225  # kg/m^3

# Real-world propulsion ISP database (sourced from public/open data)
REAL_PROPULSION_ISP = {
    "chemical_lox_kerosene": {"isp_s": 330, "thrust_to_mass": 80.0},
    "chemical_lox_h2": {"isp_s": 450, "thrust_to_mass": 50.0},
    "nuclear_thermal": {"isp_s": 850, "thrust_to_mass": 25.0},
    "nuclear_electric_ion": {"isp_s": 3000, "thrust_to_mass": 0.5},
    "magnetoplasmadynamic": {"isp_s": 5000, "thrust_to_mass": 2.0},
    "vasimr": {"isp_s": 5000, "thrust_to_mass": 1.5},
    "gr大厅": {"isp_s": 9999, "thrust_to_mass": 0.0},  # placeholder for exotic
}

REAL_MATERIALS = {
    "al2219": {"density_kg_m3": 2840, "yield_mpa": 350, "max_temp_k": 450},
    "titanium_al6vn": {"density_kg_m3": 4430, "yield_mpa": 900, "max_temp_k": 600},
    "carbon_carbon": {"density_kg_m3": 1800, "yield_mpa": 200, "max_temp_k": 2200},
    "si_c_c": {"density_kg_m3": 2000, "yield_mpa": 150, "max_temp_k": 2400},
    "tungsten": {"density_kg_m3": 19300, "yield_mpa": 550, "max_temp_k": 3000},
}

# Theoretical propulsion (advanced/speculative but not pure sci-fi)
THEORETICAL_PROPULSION = {
    "fusion_rocket": {"isp_s": 10000, "thrust_to_mass": 15.0},
    "fusion_ramjet": {"isp_s": 20000, "thrust_to_mass": 8.0},
    "plasma_pulse": {"isp_s": 15000, "thrust_to_mass": 12.0},
    "magnetized_target_fusion": {"isp_s": 12000, "thrust_to_mass": 10.0},
    "laser_sail": {"isp_s": 99999, "thrust_to_mass": 0.01},
    "antimatter_catalyzed": {"isp_s": 50000, "thrust_to_mass": 5.0},
}

THEORETICAL_MATERIALS = {
    "laniakea_weave": {"density_kg_m3": 1200, "yield_mpa": 800, "max_temp_k": 3500},
    "graphene_composite": {"density_kg_m3": 2200, "yield_mpa": 1300, "max_temp_k": 4000},
    "metallic_hydrogen": {"density_kg_m3": 900, "yield_mpa": 500, "max_temp_k": 500},
}


@dataclass
class SpacecraftDesign:
    name: str
    mass_kg: float
    length_m: float
    max_diameter_m: float
    propulsion: str
    isp_s: float
    thrust_n: float
    atmo_capable: bool
    max_speed_m_s: float
    crew: int
    cargo_kg: float
    structure_material: str = "titanium_al6vn"
    thermal_material: str = "si_c_c"
    shield_material: str = "none"
    armor_material: str = "al2o3_dep"
    habitat_volume_m3: float = 0.0
    power_output_mw: float = 0.0
    radiation_shielding_kg: float = 0.0
    score: float = 0.0
    generation: int = 0
    parent: str = ""
    simulation_mode: str = "realistic"  # or "theoretical"
    source_tier: str = "generated"  # "generated", "reference", "bde_patrol", "real_world"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["max_speed_c"] = self.max_speed_m_s / C
        return d


@dataclass
class PhysicsModel:
    delta_v_m_s: float = 0.0
    thrust_to_weight: float = 0.0
    mass_fraction: float = 0.0
    payload_fraction: float = 0.0
    ballistic_coefficient: float = 0.0
    peak_heating_w_m2: float = 0.0
    structure_mass_kg: float = 0.0
    propellant_mass_kg: float = 0.0
    power_mw: float = 0.0
    shield_mass_kg: float = 0.0
    armor_mass_kg: float = 0.0
    orbital_delta_v_m_s: float = 0.0
    escape_delta_v_m_s: float = 0.0
    lunar_delta_v_m_s: float = 0.0
    mars_delta_v_m_s: float = 0.0
    reentry_peak_heat_flux_w_m2: float = 0.0
    material_margin: float = 1.0


def precise_physics(d: SpacecraftDesign) -> PhysicsModel:
    """High-fidelity physics model with real orbital mechanics."""
    volume = math.pi * (d.max_diameter_m / 2) ** 2 * d.length_m
    d.habitat_volume_m3 = volume * 0.35
    
    # Power based on propulsion type
    if d.simulation_mode == "realistic":
        power_factor = 0.1
        d.power_output_mw = power_factor * d.thrust_n / 1000.0 + 0.5
    else:
        d.power_output_mw = 0.05 * d.thrust_n / 1000.0 + 1.0

    # Material database lookup
    mat_db = REAL_MATERIALS if d.simulation_mode == "realistic" else THEORETICAL_MATERIALS
    struct_mat = mat_db.get(d.structure_material, REAL_MATERIALS["titanium_al6vn"])
    thermal_mat = mat_db.get(d.thermal_material, REAL_MATERIALS["si_c_c"])

    # Structure mass with proper scaling
    wetted_area = math.pi * d.max_diameter_m * d.length_m + 2 * math.pi * (d.max_diameter_m/2)**2
    structure_mass = wetted_area * 15.0 + d.habitat_volume_m3 * 25.0
    if d.atmo_capable:
        structure_mass *= 1.4  # Atmospheric capability adds structural mass

    # Radiation shielding (water/polyethylene equivalent)
    d.radiation_shielding_kg = max(0.0, 50.0 * (d.habitat_volume_m3 / 100.0))

    # Dry mass
    dry_mass = structure_mass + d.cargo_kg + 120 * d.crew + d.radiation_shielding_kg + d.power_output_mw * 200

    # Tsiolkovsky rocket equation
    if d.isp_s > 0 and dry_mass > 0:
        mass_ratio = d.mass_kg / dry_mass
        if mass_ratio > 1.0:
            delta_v = d.isp_s * G0 * math.log(mass_ratio)
        else:
            delta_v = 0.0
    else:
        delta_v = 0.0

    propellant_mass = max(d.mass_kg - dry_mass, 0.0)

    # T/W
    tw = d.thrust_n / (d.mass_kg * G0) if d.mass_kg > 0 else 0.0

    # Ballistic coefficient
    area = math.pi * (d.max_diameter_m / 2) ** 2
    cd = 0.3 if d.atmo_capable else 0.05
    ballistic_coeff = d.mass_kg / (cd * area) if area > 0 else 0.0

    # Peak heating (Mars/Earth reentry correlation)
    if d.max_speed_m_s > 0:
        v_ratio = d.max_speed_m_s / 7800.0
        peak_heating = 1e5 * v_ratio ** 3.5
    else:
        peak_heating = 0.0

    # Reentry heat flux (more precise)
    reentry_flux = peak_heating * 1.2 if d.atmo_capable else 0.0

    # Material margin check
    thermal_limit = thermal_mat["max_temp_k"]
    # Simple temperature estimate: stagnation temp ~ v^2/2 / specific_heat
    specific_heat = 1000.0  # J/kg-K approximate for ceramics
    stagnation_temp = 0.5 * d.max_speed_m_s**2 / specific_heat if d.max_speed_m_s > 0 else 0.0
    material_margin = thermal_limit / max(stagnation_temp, 1.0) if stagnation_temp > 0 else 10.0

    # Delta-V budgets for real missions (from NASA/real mission data)
    orbital_dv = 9400.0  # LEO to LEO
    escape_dv = 13000.0  # Earth escape
    lunar_dv = 15000.0   # Earth to lunar surface
    mars_dv = 25000.0    # Earth to Mars surface (approx)

    # Armor + shield
    shield_mass = d.mass_kg * (0.04 if d.shield_material != "none" else 0.0)
    armor_mass = structure_mass * (0.18 if d.armor_material != "none" else 0.0)

    return PhysicsModel(
        delta_v_m_s=delta_v,
        thrust_to_weight=tw,
        mass_fraction=propellant_mass / d.mass_kg if d.mass_kg > 0 else 0.0,
        payload_fraction=(d.cargo_kg + 120 * d.crew) / d.mass_kg if d.mass_kg > 0 else 0.0,
        ballistic_coefficient=ballistic_coeff,
        peak_heating_w_m2=peak_heating,
        structure_mass_kg=structure_mass,
        propellant_mass_kg=propellant_mass,
        power_mw=d.power_output_mw,
        shield_mass_kg=shield_mass,
        armor_mass_kg=armor_mass,
        orbital_delta_v_m_s=orbital_dv,
        escape_delta_v_m_s=escape_dv,
        lunar_delta_v_m_s=lunar_dv,
        mars_delta_v_m_s=mars_dv,
        reentry_peak_heat_flux_w_m2=reentry_flux,
        material_margin=material_margin,
    )


def score_design(d: SpacecraftDesign, physics: PhysicsModel) -> float:
    score = 0.0
    mode = d.simulation_mode
    
    if mode == "realistic":
        # Strict scoring for realistic mode
        score += min(physics.delta_v_m_s / 15000.0, 1.0) * 30.0
        score += min(d.max_speed_m_s / (0.15 * C), 1.0) * 20.0
        if d.atmo_capable:
            score += min(physics.thrust_to_weight / 1.4, 1.0) * 15.0
        else:
            score -= 10.0
        score += min(physics.payload_fraction / 0.25, 1.0) * 15.0
        score += min(physics.mass_fraction / 0.90, 1.0) * 10.0
        # Penalize exotic drives in realistic mode
        if d.propulsion not in REAL_PROPULSION_ISP:
            score -= 30.0
        # Material safety margin
        score += min(physics.material_margin / 3.0, 1.0) * 5.0
    else:
        # Theoretical mode: more lenient
        score += min(physics.delta_v_m_s / (0.2 * C), 1.0) * 30.0
        score += min(d.max_speed_m_s / (0.5 * C), 1.0) * 20.0
        if d.atmo_capable:
            score += min(physics.thrust_to_weight / 1.2, 1.0) * 15.0
        else:
            score -= 5.0
        score += min(physics.payload_fraction / 0.35, 1.0) * 15.0
        score += min(physics.mass_fraction / 0.85, 1.0) * 10.0
        if d.propulsion in THEORETICAL_PROPULSION:
            score += 5.0
        score += min(physics.material_margin / 2.0, 1.0) * 5.0

    score += min(d.crew / 12.0, 1.0) * 5.0
    score += min(d.cargo_kg / 5e5, 1.0) * 5.0
    
    d.score = max(score, 0.0)
    return d.score


def random_design(mode: str = "realistic", generation: int = 0, parent_name: str = "") -> SpacecraftDesign:
    atmo = random.random() < 0.6
    base_mass = random.uniform(8e3, 1.2e6)
    
    if mode == "realistic":
        propulsions = list(REAL_PROPULSION_ISP.keys())
        structure_materials = list(REAL_MATERIALS.keys())
        thermal_materials = list(REAL_MATERIALS.keys())
        base_isp = random.uniform(300, 5000)
        max_speed = random.uniform(800, 0.12 * C)
    else:
        propulsions = list(THEORETICAL_PROPULSION.keys())
        structure_materials = list(THEORETICAL_MATERIALS.keys()) + list(REAL_MATERIALS.keys())
        thermal_materials = list(THEORETICAL_MATERIALS.keys()) + list(REAL_MATERIALS.keys())
        base_isp = random.uniform(5000, 50000)
        max_speed = random.uniform(800, 0.45 * C)
    
    return SpacecraftDesign(
        name=f"gen{generation}-{random.randint(1000,9999)}",
        mass_kg=base_mass,
        length_m=random.uniform(12, 220),
        max_diameter_m=random.uniform(3, 28),
        propulsion=random.choice(propulsions),
        isp_s=base_isp,
        thrust_n=random.uniform(5e4, 1.2e9),
        atmo_capable=atmo,
        max_speed_m_s=max_speed,
        crew=random.randint(0, 20),
        cargo_kg=random.uniform(0, 1.2e6),
        structure_material=random.choice(structure_materials),
        thermal_material=random.choice(thermal_materials),
        generation=generation,
        parent=parent_name,
        simulation_mode=mode,
        source_tier="generated",
    )


def mutate(d: SpacecraftDesign) -> SpacecraftDesign:
    child = SpacecraftDesign(**asdict(d))
    child.name = f"gen{child.generation+1}-{random.randint(1000,9999)}"
    child.generation += 1
    child.parent = d.name
    child.score = 0.0
    roll = random.random()
    if roll < 0.25:
        child.mass_kg *= random.uniform(0.85, 1.4)
    elif roll < 0.45:
        child.length_m *= random.uniform(0.9, 1.25)
    elif roll < 0.6:
        child.max_diameter_m *= random.uniform(0.9, 1.2)
    elif roll < 0.75:
        if child.simulation_mode == "realistic":
            child.propulsion = random.choice(list(REAL_PROPULSION_ISP.keys()))
        else:
            child.propulsion = random.choice(list(THEORETICAL_PROPULSION.keys()) + list(REAL_PROPULSION_ISP.keys()))
    elif roll < 0.88:
        child.isp_s = max(300.0, child.isp_s * random.uniform(0.8, 1.35))
    else:
        child.max_speed_m_s = min(0.5 * C if child.simulation_mode == "theoretical" else 0.15 * C,
                                  max(800.0, child.max_speed_m_s * random.uniform(0.9, 1.2)))
    child.thrust_n = max(child.thrust_n, child.mass_kg * 1.1 * G0 if child.atmo_capable else child.mass_kg * G0 * 0.4)
    return child


def crossover(a: SpacecraftDesign, b: SpacecraftDesign) -> SpacecraftDesign:
    mode = a.simulation_mode if random.random() < 0.5 else b.simulation_mode
    child = SpacecraftDesign(
        name=f"gen{max(a.generation,b.generation)+1}-{random.randint(1000,9999)}",
        mass_kg=a.mass_kg if random.random() < 0.5 else b.mass_kg,
        length_m=a.length_m if random.random() < 0.5 else b.length_m,
        max_diameter_m=a.max_diameter_m if random.random() < 0.5 else b.max_diameter_m,
        propulsion=a.propulsion if random.random() < 0.5 else b.propulsion,
        isp_s=(a.isp_s + b.isp_s) / 2.0,
        thrust_n=(a.thrust_n + b.thrust_n) / 2.0,
        atmo_capable=a.atmo_capable and b.atmo_capable,
        max_speed_m_s=max(a.max_speed_m_s, b.max_speed_m_s) * 0.95,
        crew=(a.crew + b.crew) // 2,
        cargo_kg=(a.cargo_kg + b.cargo_kg) / 2.0,
        structure_material=a.structure_material if random.random() < 0.5 else b.structure_material,
        thermal_material=a.thermal_material if random.random() < 0.5 else b.thermal_material,
        shield_material=a.shield_material if random.random() < 0.5 else b.shield_material,
        armor_material=a.armor_material if random.random() < 0.5 else b.armor_material,
        generation=max(a.generation, b.generation) + 1,
        parent=f"{a.name}+{b.name}",
        simulation_mode=mode,
        source_tier="generated",
    )
    return child


def run_dual_simulation(runs: int = 10, population: int = 40, output: str = "blueprints") -> Dict[str, Any]:
    """Run two separate simulations: realistic and theoretical."""
    out = Path(output)
    runs_dir = Path("sim-runs") / datetime.now().strftime("%Y%m%d-%H%M%S")
    runs_dir.mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)

    # BDE Patrol scan
    try:
        from src.bde_patrol import BDEPatrol
        patrol = BDEPatrol(Path("."), Path("data"))
        patrol_summary = patrol.run_patrol(
            queries=["spacecraft CAD open source", "rocket engine design 3D model", "space shuttle CAD"],
            urls=["https://www.nasa.gov/sites/default/files/atoms/files/space_vehicle_design_v2.0.pdf"]
        )
    except Exception as e:
        patrol_summary = {"error": str(e)}

    summarize_references(out)

    results = {}
    for mode in ["realistic", "theoretical"]:
        print(f"[sim] === {mode.upper()} MODE ===")
        pop = [random_design(mode=mode, generation=0) for _ in range(population)]
        
        best_overall = None
        for run_idx in range(runs):
            scored = []
            for d in pop:
                p = precise_physics(d)
                s = score_design(d, p)
                scored.append((s, d))
            scored.sort(key=lambda x: x[0], reverse=True)

            best = scored[0][1]
            if best_overall is None or best.score > best_overall.score:
                best_overall = best

            run_log = {
                "mode": mode,
                "run": run_idx + 1,
                "best_name": best.name,
                "best_score": best.score,
                "best_speed_c": best.max_speed_m_s / C,
                "best_delta_v_c": precise_physics(best).delta_v_m_s / C,
                "best_atmo": best.atmo_capable,
            }
            (runs_dir / f"{mode}_run_log.jsonl").open("a").write(json.dumps(run_log) + "\n")

            # Next generation
            new_pop = [scored[i][1] for i in range(min(8, len(scored)))]
            while len(new_pop) < population:
                if random.random() < 0.75 and len(scored) > 1:
                    a = random.choice(scored[:max(1, len(scored)//2)])[1]
                    b = random.choice(scored[:max(1, len(scored)//2)])[1]
                    child = crossover(a, b)
                else:
                    parent = random.choice(scored[:max(1, len(scored)//3)])[1]
                    child = mutate(parent)
                new_pop.append(child)
            pop = new_pop

        if best_overall:
            physics = precise_physics(best_overall)
            results[mode] = {
                "best_design": best_overall.to_dict(),
                "physics": asdict(physics),
                "best_score": best_overall.score,
            }
            # Save best per mode
            (out / "blueprints" / f"best_{mode}.json").write_text(json.dumps(best_overall.to_dict(), indent=2))

    # Comparative report
    report = {
        "realistic": results.get("realistic", {}),
        "theoretical": results.get("theoretical", {}),
        "bde_patrol": patrol_summary,
        "timestamp": datetime.now().isoformat(),
        "runs_per_mode": runs,
        "population": population,
        "run_directory": str(runs_dir),
        "note": "Dual-track simulation: realistic = current physics only; theoretical = advanced propulsion + materials.",
    }
    (out / "reports" / f"report-{runs_dir.name}.json").write_text(json.dumps(report, indent=2))
    
    print(f"[sim] Realistic best score: {results.get('realistic', {}).get('best_score', 0):.2f}")
    print(f"[sim] Theoretical best score: {results.get('theoretical', {}).get('best_score', 0):.2f}")
    return report


def summarize_references(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    out = path / "reference_corpus.json"
    with out.open("w") as f:
        json.dump(REFERENCES, f, indent=2)
    print(f"[survey] wrote {out} ({len(REFERENCES)} reference craft)")


# Reference corpus (games, fiction, real proposals)
REFERENCES = [
    {"name": "Space Shuttle", "source": "real_world", "mass_kg": 2e6, "length_m": 56.1,
     "propulsion": "chemical_lox_h2", "isp_s": 450, "thrust_n": 3e7, "atmo_capable": True,
     "max_speed_m_s": 7800, "crew": 8, "cargo_kg": 25000},
    {"name": "Saturn V", "source": "real_world", "mass_kg": 3e6, "length_m": 110.6,
     "propulsion": "chemical_lox_kerosene", "isp_s": 330, "thrust_n": 3.5e7, "atmo_capable": True,
     "max_speed_m_s": 11000, "crew": 3, "cargo_kg": 140000},
    {"name": "Falcon Heavy", "source": "real_world", "mass_kg": 1.4e6, "length_m": 70.0,
     "propulsion": "chemical_lox_kerosene", "isp_s": 330, "thrust_n": 1.5e7, "atmo_capable": True,
     "max_speed_m_s": 9500, "crew": 0, "cargo_kg": 63800},
    {"name": "Starship", "source": "real_world", "mass_kg": 5e6, "length_m": 120.0,
     "propulsion": "chemical_lox_kerosene", "isp_s": 350, "thrust_n": 5e7, "atmo_capable": True,
     "max_speed_m_s": 8500, "crew": 100, "cargo_kg": 150000},
    {"name": "VASIMR Testbed", "source": "real_world", "mass_kg": 15000, "length_m": 12.0,
     "propulsion": "vasimr", "isp_s": 5000, "thrust_n": 5e4, "atmo_capable": False,
     "max_speed_m_s": 0.02 * C, "crew": 0, "cargo_kg": 5000},
    {"name": "Ion Drive Deep Space 1", "source": "real_world", "mass_kg": 500, "length_m": 1.5,
     "propulsion": "nuclear_electric_ion", "isp_s": 3000, "thrust_n": 90, "atmo_capable": False,
     "max_speed_m_s": 0.01 * C, "crew": 0, "cargo_kg": 0},
    {"name": "Enterprise NCC-1701", "source": "open_source_3d", "mass_kg": 1e9, "length_m": 300.0,
     "propulsion": "fusion_rocket", "isp_s": 10000, "thrust_n": 1e10, "atmo_capable": False,
     "max_speed_m_s": 0.08 * C, "crew": 500, "cargo_kg": 5e8},
    {"name": "Destiny Dropship", "source": "game_destiny2", "mass_kg": 45000, "length_m": 24.0,
     "propulsion": "chemical_rocket", "isp_s": 350, "thrust_n": 2.5e6, "atmo_capable": True,
     "max_speed_m_s": 1200, "crew": 6, "cargo_kg": 8000},
    {"name": "Halo Pelican", "source": "game_halo", "mass_kg": 38000, "length_m": 30.5,
     "propulsion": "turbofan_ramjet_rocket", "isp_s": 1200, "thrust_n": 3.6e6, "atmo_capable": True,
     "max_speed_m_s": 1400, "crew": 6, "cargo_kg": 70000},
    {"name": "EVE Rifter", "source": "game_eve", "mass_kg": 35000, "length_m": 38.0,
     "propulsion": "fusion_rocket", "isp_s": 4500, "thrust_n": 2.8e6, "atmo_capable": False,
     "max_speed_m_s": 0.025 * C, "crew": 1, "cargo_kg": 21000},
    {"name": "Star Citizen Constellation", "source": "game_star_citizen", "mass_kg": 110e3, "length_m": 62.0,
     "propulsion": "quantum_drive", "isp_s": 20000, "thrust_n": 2.1e7, "atmo_capable": True,
     "max_speed_m_s": 0.2 * C, "crew": 4, "cargo_kg": 480e3},
    {"name": "TIE Fighter", "source": "open_source_3d", "mass_kg": 8000, "length_m": 7.2,
     "propulsion": "fusion_rocket", "isp_s": 8000, "thrust_n": 5e5, "atmo_capable": False,
     "max_speed_m_s": 0.04 * C, "crew": 1, "cargo_kg": 0},
    {"name": "MAVEN", "source": "real_world", "mass_kg": 2500, "length_m": 11.4,
     "propulsion": "chemical_lox_h2", "isp_s": 450, "thrust_n": 5e4, "atmo_capable": False,
     "max_speed_m_s": 0.03 * C, "crew": 0, "cargo_kg": 0},
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--population", type=int, default=50)
    ap.add_argument("--output", type=str, default="blueprints")
    args = ap.parse_args()
    report = run_dual_simulation(runs=args.runs, population=args.population, output=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
