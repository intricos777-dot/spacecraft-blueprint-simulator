import sys, json, math, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from simulator import precise_physics, score_design, SpacecraftDesign


class TestPhysics(unittest.TestCase):
    def test_realistic_basic(self):
        d = SpacecraftDesign(
            name="test", mass_kg=250000.0, length_m=20.0, max_diameter_m=5.0,
            propulsion="chemical_lox_kerosene", isp_s=330, thrust_n=1e6,
            atmo_capable=True, max_speed_m_s=8000, crew=2, cargo_kg=1e5,
            simulation_mode="realistic",
        )
        p = precise_physics(d)
        self.assertGreater(p.delta_v_m_s, 0)
        self.assertGreater(p.thrust_to_weight, 0)
        self.assertGreater(p.ballistic_coefficient, 0)

    def test_theoretical_basic(self):
        d = SpacecraftDesign(
            name="test", mass_kg=250000.0, length_m=20.0, max_diameter_m=5.0,
            propulsion="fusion_rocket", isp_s=10000, thrust_n=1e6,
            atmo_capable=False, max_speed_m_s=0.1, crew=2, cargo_kg=1e5,
            simulation_mode="theoretical",
        )
        p = precise_physics(d)
        self.assertGreater(p.delta_v_m_s, 0)

    def test_score_non_negative(self):
        d = SpacecraftDesign(
            name="test", mass_kg=250000.0, length_m=20.0, max_diameter_m=5.0,
            propulsion="chemical_lox_kerosene", isp_s=330, thrust_n=1e6,
            atmo_capable=True, max_speed_m_s=8000, crew=2, cargo_kg=1e5,
            simulation_mode="realistic",
        )
        p = precise_physics(d)
        self.assertGreaterEqual(score_design(d, p), 0.0)

    def test_realistic_penalizes_exotic_propulsion(self):
        d = SpacecraftDesign(
            name="test", mass_kg=250000.0, length_m=20.0, max_diameter_m=5.0,
            propulsion="fusion_rocket", isp_s=10000, thrust_n=1e6,
            atmo_capable=True, max_speed_m_s=0.1, crew=2, cargo_kg=1e5,
            simulation_mode="realistic",
        )
        p = precise_physics(d)
        self.assertLess(score_design(d, p), 50.0)


if __name__ == "__main__":
    unittest.main()
