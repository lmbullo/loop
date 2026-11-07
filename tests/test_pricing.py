import json
import os
import unittest

from harness import config, pricing


class PricingTest(unittest.TestCase):
    def test_rates_come_from_manifest(self):
        with open(config.asset("manifest.json"), encoding="utf-8") as f:
            expected = json.load(f)["cost_model"]["pricing_per_1M"]
        self.assertEqual(pricing.rates(), expected)

    def test_rates_returns_a_copy(self):
        rates = pricing.rates()
        rates["cache_hit"] = 999
        self.assertNotEqual(pricing.rates()["cache_hit"], 999)

    def test_cost_formula(self):
        self.assertAlmostEqual(pricing.cost(0, 0, 0), 0.0)
        self.assertAlmostEqual(pricing.cost(1_000_000, 0, 0), 0.006)
        self.assertAlmostEqual(pricing.cost(0, 1_000_000, 0), 0.3)
        self.assertAlmostEqual(pricing.cost(0, 0, 1_000_000), 1.2)
        self.assertAlmostEqual(pricing.cost(1_000_000, 1_000_000, 1_000_000), 1.506)

    def test_cost_accepts_ints(self):
        self.assertAlmostEqual(pricing.cost(10, 20, 30), (10 * 0.006 + 20 * 0.3 + 30 * 1.2) / 1e6)


if __name__ == "__main__":
    unittest.main()
