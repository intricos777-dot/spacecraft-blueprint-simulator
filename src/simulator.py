#!/usr/bin/env python3
"""
Spacecraft Blueprint Simulator
Self-looping design space explorer for an atmospheric-capable spacecraft
targeting 0.5c cruise with plasma propulsion.

Mode:
  - survey   : ingest reference designs
  - optimize : run autonomous optimization loop
  - report   : summarize best blueprints
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
from typing import List, Dict, Any

# Physics constants
C = 299792458.0  # m/s
G0 = 9.80665     # m/s^2
EARTH_R = 6371000.0
MU = 3.986004418e14
R_EARTH = 6371000.0

# Reference spacecraft corpus (games, fiction, real proposals)
# Each entry preserves the "flavor" of Destiny 2, Halo, EVE, Elite, etc.
REFERENCES = [
    {"name": "Destiny - Dropship", "game": "Destiny 2", "mass_kg": 45000, "length_m": 24.0,
     "propulsion": "chemical_rocket", "isp_s": 350, "thrust_n": 2.5e6, "atmo_capable": True,
     "max_speed_m_s": 1200, "crew": 6, "cargo_kg": 8000},
    {"name": "Destiny - Interceptor", "game": "Destiny 2", "mass_kg": 18000, "length_m": 18.0,
     "propulsion": "chemical_rocket", "isp_s": 340, "thrust_n": 1.8e6, "atmo_capable": True,
     "max_speed_m_s": 1100, "crew": 1, "cargo_kg": 2000},
    {"name": "Destiny - Palamar", "game": "Destiny 2", "mass_kg": 120000, "length_m": 55.0,
     "propulsion": "fusion_ramjet", "isp_s": 8000, "thrust_n": 4.0e7, "atmo_capable": False,
     "max_speed_m_s": 0.08 * C, "crew": 40, "cargo_kg": 95000},
    {"name": "Destiny - Harvester", "game": "Destiny 2", "mass_kg": 2.5e6, "length_m": 180.0,
     "propulsion": "fusion_ramjet", "isp_s": 9000, "thrust_n": 3.0e8, "atmo_capable": False,
     "max_speed_m_s": 0.12 * C, "crew": 200, "cargo_kg": 1.8e6},
    {"name": "Halo - Pelican", "game": "Halo", "mass_kg": 38e3, "length_m": 30.5,
     "propulsion": "turbofan_ramjet_rocket", "isp_s": 1200, "thrust_n": 3.6e6, "atmo_capable": True,
     "max_speed_m_s": 1400, "crew": 6, "cargo_kg": 70e3},
    {"name": "Halo - Banshee", "game": "Halo", "mass_kg": 500, "length_m": 4.5,
     "propulsion": "gravitic_anti_grav", "isp_s": 9999, "thrust_n": 4.5e4, "atmo_capable": True,
     "max_speed_m_s": 280, "crew": 1, "cargo_kg": 120},
    {"name": "Halo - Lighter", "game": "Halo", "mass_kg": 5200, "length_m": 10.0,
     "propulsion": "fusion_rocket", "isp_s": 5000, "thrust_n": 5.0e6, "atmo_capable": True,
     "max_speed_m_s": 0.04 * C, "crew": 2, "cargo_kg": 15000},
    {"name": "EVE - Rifter", "game": "EVE Online", "mass_kg": 35e3, "length_m": 38.0,
     "propulsion": "fusion_rocket", "isp_s": 4500, "thrust_n": 2.8e6, "atmo_capable": False,
     "max_speed_m_s": 0.025 * C, "crew": 1, "cargo_kg": 21000},
    {"name": "EVE - Megathron", "game": "EVE Online", "mass_kg": 14e6, "length_m": 430.0,
     "propulsion": "fusion_ramjet", "isp_s": 12000, "thrust_n": 5.5e10, "atmo_capable": False,
     "max_speed_m_s": 0.06 * C, "crew": 3, "cargo_kg": 420000},
    {"name": "Elite - Asp Explorer", "game": "Elite Dangerous", "mass_kg": 350e3, "length_m": 52.0,
     "propulsion": "fusion_rocket", "isp_s": 7000, "thrust_n": 1.2e7, "atmo_capable": False,
     "max_speed_m_s": 0.05 * C, "crew": 2, "cargo_kg": 128e3},
    {"name": "Star Citizen - Constellation", "game": "Star Citizen", "mass_kg": 110e3, "length_m": 62.0,
     "propulsion": "quantum_drive", "isp_s": 20000, "thrust_n": 2.1e7, "atmo_capable": True,
     "max_speed_m_s": 0.2 * C, "crew": 4, "cargo_kg": 480e3},
    {"name": "Star Citizen - 890 Jump", "game": "Star Citizen", "mass_kg": 1.5e6, "length_m": 110.0,
     "propulsion": "quantum_drive", "isp_s": 22000, "thrust_n": 4.5e8, "atmo_capable": True,
     "max_speed_m_s": 0.22 * C, "crew": 12, "cargo_kg": 12e3},
    {"name": "Stellaris - Science Nexus", "game": "Stellaris", "mass_kg": 8.5e9, "length_m": 12000.0,
     "propulsion": "ftl_hyperspace", "isp_s": 999999, "thrust_n": 1.2e18, "atmo_capable": False,
     "max_speed_m_s": 50.0 * C, "crew": 2000, "cargo_kg": 3.8e12},
]


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


def estimate_physics(d: SpacecraftDesign) -> PhysicsModel:
    """Very rough first-principles estimates."""
    volume = math.pi * (d.max_diameter_m / 2) ** 2 * d.length_m
    d.habitat_volume_m3 = volume * 0.35
    d.power_output_mw = 2.0 + d.isp_s * 0.15 + d.thrust_n / 5e8

    # Structure
    if "carbon" in d.structure_material or "titanium" in d.structure_material:
        structure_mass = d.mass_kg * 0.18
    else:
        structure_mass = d.mass_kg * 0.22
    structure_mass += d.habitat_volume_m3 * 18.0

    # Propellant
    dry_mass_guess = structure_mass + d.cargo_kg + 120 * d.crew + d.radiation_shielding_kg
    delta_v = d.isp_s * G0 * math.log(max(d.mass_kg, dry_mass_guess + 1.0) / max(dry_mass_guess, 1.0))
    propellant_mass = max(d.mass_kg - dry_mass_guess, 0.0)

    # T/W at sea level if atmo capable
    if d.atmo_capable:
        tw = d.thrust_n / (d.mass_kg * G0)
    else:
        tw = d.thrust_n / (d.mass_kg * G0)

    # Ballistic coeff = m / Cd * A. Use Cd=0.3, A=pi*r^2
    area = math.pi * (d.max_diameter_m / 2) ** 2
    ballistic_coeff = d.mass_kg / (0.3 * area) if area > 0 else 0.0

    # Peak heating (stagnation) ~ rho^0.5 * v^3, scaled to LEO
    peak_heating = 1e5 * (d.max_speed_m_s / 7800.0) ** 3.0

    # Armor + shield rough mass
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
    )


def score_design(d: SpacecraftDesign, physics: PhysicsModel) -> float:
    score = 0.0
    # Speed
    score += min(physics.delta_v_m_s / (0.15 * C), 1.0) * 30.0
    score += min(d.max_speed_m_s / (0.5 * C), 1.0) * 20.0
    # T/W for atmo
    if d.atmo_capable:
        score += min(physics.thrust_to_weight / 1.4, 1.0) * 15.0
    else:
        score -= 10.0
    # Practicality
    score += min(physics.payload_fraction / 0.35, 1.0) * 15.0
    score += min(physics.mass_fraction / 0.85, 1.0) * 10.0
    # Realism penalty for pure sci-fi drives with no path
    if d.propulsion in {"gravitic_anti_grav", "ftl_hyperspace"}:
        score -= 25.0
    if d.propulsion in {"fusion_ramjet", "quantum_drive"}:
        score += 5.0
    # Crew/cargo utility
    score += min(d.crew / 12.0, 1.0) * 5.0
    score += min(d.cargo_kg / 5e5, 1.0) * 5.0
    d.score = max(score, 0.0)
    return d.score


def random_design(generation: int = 0, parent_name: str = "") -> SpacecraftDesign:
    atmo = random.random() < 0.6
    base_mass = random.uniform(8e3, 1.2e6)
    propulsions = [
        "chemical_rocket", "nuclear_thermal", "nuclear_pulse",
        "fusion_rocket", "fusion_ramjet", "magnetoplasmadynamic",
        "vlasov_amg", "quantum_drive", "plasma_pulse"
    ]
    structure_materials = [
        "al2219", "titanium_al6vn", "carbon_carbon", "laniakea_weave"
    ]
    thermal_materials = ["sic_cmc", "hiti", "transpiration"]
    shield_materials = ["none", "mag", "plasma", "ablative"]
    armor_materials = ["none", "si_c_c", "al2o3_dep", "tungsten_dep"]
    return SpacecraftDesign(
        name=f"gen{generation}-{random.randint(1000,9999)}",
        mass_kg=base_mass,
        length_m=random.uniform(12, 220),
        max_diameter_m=random.uniform(3, 28),
        propulsion=random.choice(propulsions),
        isp_s=random.uniform(300, 25000),
        thrust_n=random.uniform(5e4, 1.2e9),
        atmo_capable=atmo,
        max_speed_m_s=random.uniform(800, 0.45 * C),
        crew=random.randint(0, 20),
        cargo_kg=random.uniform(0, 1.2e6),
        structure_material=random.choice(structure_materials),
        thermal_material=random.choice(thermal_materials),
        shield_material=random.choice(shield_materials),
        armor_material=random.choice(armor_materials),
        generation=generation,
        parent=parent_name,
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
        child.propulsion = random.choice([
            "chemical_rocket", "nuclear_thermal", "nuclear_pulse",
            "fusion_rocket", "fusion_ramjet", "magnetoplasmadynamic",
            "vlasov_amg", "plasma_pulse"
        ])
    elif roll < 0.88:
        child.isp_s = max(300.0, child.isp_s * random.uniform(0.8, 1.35))
    else:
        child.max_speed_m_s = min(0.5 * C, max(800.0, child.max_speed_m_s * random.uniform(0.9, 1.2)))
    child.thrust_n = max(child.thrust_n, child.mass_kg * 1.1 * G0 if child.atmo_capable else child.mass_kg * G0 * 0.4)
    return child


def crossover(a: SpacecraftDesign, b: SpacecraftDesign) -> SpacecraftDesign:
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
    )
    return child


def summarize_references(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    out = path / "reference_corpus.json"
    with out.open("w") as f:
        json.dump(REFERENCES, f, indent=2)
    print(f"[survey] wrote {out} ({len(REFERENCES)} reference craft)")


def run_simulation(runs: int = 10, population: int = 40, output: str = "blueprints") -> Dict[str, Any]:
    out = Path(output)
    runs_dir = Path("sim-runs") / datetime.now().strftime("%Y%m%d-%H%M%S")
    runs_dir.mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)

    summarize_references(out)

    # Seed population
    pop: List[SpacecraftDesign] = [random_design(generation=0) for _ in range(population)]
    # Inject references
    for r in REFERENCES:
        pop.append(SpacecraftDesign(
            name=r["name"], mass_kg=r["mass_kg"], length_m=r["length_m"],
            max_diameter_m=r["length_m"] * 0.18, propulsion=r["propulsion"],
            isp_s=r["isp_s"], thrust_n=r["thrust_n"], atmo_capable=r["atmo_capable"],
            max_speed_m_s=r["max_speed_m_s"], crew=r["crew"], cargo_kg=r["cargo_kg"],
            generation=0, parent="reference",
        ))

    best_overall: SpacecraftDesign | None = None
    if not pop:
        raise RuntimeError("population empty")

    for run_idx in range(runs):
        scored: List[tuple[float, SpacecraftDesign]] = []
        for d in pop:
            p = estimate_physics(d)
            s = score_design(d, p)
            scored.append((s, d))
        scored.sort(key=lambda x: x[0], reverse=True)

        best = scored[0][1]
        if best_overall is None or best.score > best_overall.score:
            best_overall = best

        run_log = {
            "run": run_idx + 1,
            "best_name": best.name,
            "best_score": best.score,
            "best_speed_c": best.max_speed_m_s / C,
            "best_delta_v_c": estimate_physics(best).delta_v_m_s / C,
            "best_atmo": best.atmo_capable,
            "population": len(pop),
        }
        (runs_dir / "run_log.jsonl").open("a").write(json.dumps(run_log) + "\n")

        # Next generation
        new_pop: List[SpacecraftDesign] = [scored[i][1] for i in range(min(8, len(scored)))]
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

        if (run_idx + 1) % max(1, runs // 10) == 0 or run_idx == runs - 1:
            print(f"[sim] run {run_idx+1}/{runs} best={best.name} score={best.score:.2f} "
                  f"speed={best.max_speed_m_s/C:.3f}c delta_v={estimate_physics(best).delta_v_m_s/C:.3f}c")

    assert best_overall is not None
    blueprints_dir = Path(out / "blueprints")
    blueprints_dir.mkdir(parents=True, exist_ok=True)
    (blueprints_dir / "best.json").write_text(json.dumps(best_overall.to_dict(), indent=2))

    physics = estimate_physics(best_overall)
    report = {
        "best_design": best_overall.to_dict(),
        "physics": asdict(physics),
        "run_directory": str(runs_dir),
        "timestamp": datetime.now().isoformat(),
        "note": "Blend of theoretical drive scaling + realistic structural/thermal/propellant budgets.",
    }
    (out / "reports" / f"report-{runs_dir.name}.json").write_text(json.dumps(report, indent=2))
    print(f"[sim] best blueprint: {best_overall.name} score={best.score:.2f}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--population", type=int, default=50)
    ap.add_argument("--output", type=str, default="blueprints")
    args = ap.parse_args()
    report = run_simulation(runs=args.runs, population=args.population, output=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
