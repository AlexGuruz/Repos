"""Tests for lib.projection_layer2_recovery."""
from __future__ import annotations

import unittest

from lib.projection_layer2_recovery import (
    avg_monthly_units_sold,
    layer2_row,
    months_in_window_span,
    recovery_bucket,
    usable_cog_cents,
)


class TestUsableCogCents(unittest.TestCase):
    def test_valid(self) -> None:
        self.assertEqual(usable_cog_cents(1000, 400), 400)

    def test_invalid(self) -> None:
        self.assertEqual(usable_cog_cents(1000, None), 0)
        self.assertEqual(usable_cog_cents(1000, -1), 0)
        self.assertEqual(usable_cog_cents(1000, 2000), 0)


class TestLayer2Row(unittest.TestCase):
    def test_zero_units(self) -> None:
        r = layer2_row(
            allocated_cog_usd=100.0,
            units_sold=0,
            gross_cents=0,
            cog_cents=0,
            span_inclusive_days=365,
        )
        self.assertEqual(r["trailing_units_sold"], 0)
        self.assertIsNone(r["months_to_recover_cog"])
        self.assertIsNone(r["units_from_allocation"])

    def test_no_cog_avg(self) -> None:
        r = layer2_row(
            allocated_cog_usd=100.0,
            units_sold=10,
            gross_cents=1000,
            cog_cents=0,
            span_inclusive_days=365,
        )
        self.assertIsNone(r["avg_cog_per_unit"])
        self.assertIsNone(r["units_from_allocation"])
        self.assertIsNotNone(r["avg_retail_per_unit"])

    def test_happy_path_365_day_window(self) -> None:
        # 10 units, $5 COG total => $0.50/unit; $20 gross => $2 retail/unit
        r = layer2_row(
            allocated_cog_usd=50.0,
            units_sold=10,
            gross_cents=2000,
            cog_cents=500,
            span_inclusive_days=365,
        )
        self.assertAlmostEqual(r["avg_cog_per_unit"], 0.5)  # $5/10 units
        self.assertAlmostEqual(r["avg_retail_per_unit"], 2.0)
        self.assertAlmostEqual(r["units_from_allocation"], 100.0)  # 50 / 0.5
        aum = r["avg_units_per_month"]
        self.assertIsNotNone(aum)
        assert aum is not None
        mom = r["months_to_recover_cog"]
        self.assertIsNotNone(mom)
        assert mom is not None
        self.assertAlmostEqual(mom, r["units_from_allocation"] / aum)
        self.assertAlmostEqual(r["projected_revenue_from_allocated_units_usd"], 200.0)
        self.assertAlmostEqual(r["projected_gross_profit_usd"], 150.0)


class TestRecoveryBucket(unittest.TestCase):
    def test_buckets(self) -> None:
        self.assertEqual(recovery_bucket(0.2), "Fast (<2wk)")
        self.assertEqual(recovery_bucket(1.0), "Medium (1–2mo)")
        self.assertEqual(recovery_bucket(2.5), "Moderate (2–3mo)")
        self.assertEqual(recovery_bucket(4.0), "Slow (>3mo)")
        self.assertIsNone(recovery_bucket(None))
        self.assertIsNone(recovery_bucket(float("nan")))


class TestMonthsInWindow(unittest.TestCase):
    def test_span(self) -> None:
        m = months_in_window_span(365)
        self.assertAlmostEqual(m, 365 * 12.0 / 365.25, places=5)


if __name__ == "__main__":
    unittest.main()
