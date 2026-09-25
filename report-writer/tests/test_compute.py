import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "tools" / "compute.py"
SPEC = importlib.util.spec_from_file_location("compute", MODULE)
compute = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compute)


class CoolingSweepTests(unittest.TestCase):
    def test_cooling_sweep_uses_outdoor_minus_indoor_temperature(self):
        rows = compute.sweep_t_in(
            K_cond=100,
            K_inf=0,
            T_ext=35,
            T_in_list=[24, 26, 28],
            seer=4,
            hours_day=8,
            season_days=10,
            tariff=0.25,
        )

        # Independently: 100 W/K * (35-Tin) K * 8 h/day * 10 days / 4 SEER.
        self.assertEqual([r["delta_T"] for r in rows], [11, 9, 7])
        self.assertEqual([r["el_kwh_season"] for r in rows], [22.0, 18.0, 14.0])
        self.assertEqual([r["season_eur"] for r in rows], [5.5, 4.5, 3.5])

    def test_setpoint_at_or_above_outdoor_temperature_has_no_envelope_load(self):
        rows = compute.sweep_t_in(100, 0, 25, [24, 25, 26], 4, 8, 10, 0.25)
        self.assertEqual([r["delta_T"] for r in rows], [1, 0, 0])
        self.assertEqual([r["el_kwh_season"] for r in rows], [2.0, 0.0, 0.0])

    def test_cli_emits_machine_readable_result(self):
        request = {
            "analysis_id": "sweep",
            "method": "sweep_t_in",
            "data": {
                "K_cond": 100, "K_inf": 0, "T_ext": 35,
                "T_in_list": [24], "seer": 4, "hours_day": 8,
                "season_days": 10, "tariff_eur_kwh": 0.25,
            },
            "unit": "kWh and EUR",
            "inputs": ["synthetic"],
        }
        result = subprocess.run(
            [sys.executable, str(MODULE)], input=json.dumps(request) + "\n",
            text=True, capture_output=True, check=True,
        )
        parsed = json.loads(result.stdout)
        self.assertTrue(parsed["computed"])
        self.assertEqual(parsed["value"][0]["el_kwh_season"], 22.0)


if __name__ == "__main__":
    unittest.main()
