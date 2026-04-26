"""Unit tests for stock pool allocation math and date chunking (no API)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from lib.allocate_stock_pool import (
    aggregate_by_brand,
    allocate_pool_cents_largest_remainder,
    concentration_hhi,
    iter_sold_at_date_chunks,
    validate_allocation,
)


def test_allocate_exact_sum_many_brands() -> None:
    weights = [100.0, 200.0, 300.0]
    pool = 1_800_000  # $18,000.00
    alloc = allocate_pool_cents_largest_remainder(pool, weights)
    assert sum(alloc) == pool
    assert len(alloc) == 3
    assert validate_allocation(pool, alloc) == []


def test_allocate_equal_weights() -> None:
    pool = 100
    alloc = allocate_pool_cents_largest_remainder(pool, [1.0, 1.0, 1.0])
    assert sum(alloc) == pool
    assert max(alloc) - min(alloc) <= 1


def test_allocate_zero_total_weight_splits_evenly() -> None:
    pool = 100
    alloc = allocate_pool_cents_largest_remainder(pool, [0.0, 0.0])
    assert sum(alloc) == pool
    assert alloc[0] + alloc[1] == 100


def test_date_chunks_no_overlap_full_coverage() -> None:
    tz = timezone.utc
    start = datetime(2025, 1, 1, 15, 30, tzinfo=tz)
    end = datetime(2025, 1, 10, 12, 0, tzinfo=tz)
    chunks = list(iter_sold_at_date_chunks(start, end, chunk_days=3))
    assert len(chunks) == 4
    days_covered: set[str] = set()
    for from_iso, to_iso in chunks:
        assert from_iso <= to_iso
        fd = from_iso[:10]
        td = to_iso[:10]
        d = datetime.strptime(fd, "%Y-%m-%d").date()
        end_d = datetime.strptime(td, "%Y-%m-%d").date()
        while d <= end_d:
            days_covered.add(d.isoformat())
            d += timedelta(days=1)
    assert days_covered == {f"2025-01-{i:02d}" for i in range(1, 11)}


def test_aggregate_by_brand_and_dedupe() -> None:
    nodes = [
        {"objectId": "a", "GrossPrice": 100, "Product": {"Brand": {"Name": "X"}}},
        {"objectId": "a", "GrossPrice": 100, "Product": {"Brand": {"Name": "X"}}},
        {"objectId": "b", "GrossPrice": 200, "Product": {"Brand": {"Name": "Y"}}},
    ]
    cents, lines, dups = aggregate_by_brand(nodes, dedupe=True)
    assert dups == 1
    assert cents["X"] == 100
    assert cents["Y"] == 200
    assert lines["X"] == 1
    assert lines["Y"] == 1


def test_aggregate_no_brand() -> None:
    nodes = [{"id": "1", "GrossPrice": 50, "Product": {}}]
    cents, lines, _ = aggregate_by_brand(nodes, dedupe=False)
    assert cents["(no brand)"] == 50
    assert lines["(no brand)"] == 1


def test_hhi() -> None:
    assert pytest.approx(concentration_hhi([0.5, 0.5])) == 0.5
    assert pytest.approx(concentration_hhi([1.0])) == 1.0
