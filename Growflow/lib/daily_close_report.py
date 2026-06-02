"""Daily sales + tax report aligned with GrowFlow dashboard (findOrders.CompletedAt + Total)."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from lib.allocate_stock_pool import order_item_key
from lib.growflow_queries import PAGE_SIZE, fetch_paginated

MJ_TAX_ID = "0R2d9pbrEB"
SALES_TAX_ID = "Ww8jfTZPBd"
K_MJ = 4587.10 / 4590.15
K_SALES = 6719.45 / 6455.63

ORDERS_QUERY = """
query Orders($first: Int, $after: String, $where: OrdersWhereInput) {
  findOrders(first: $first, after: $after, where: $where) {
    edges { node { objectId CompletedAt Total Subtotal Discounts Taxes } }
    pageInfo { hasNextPage endCursor }
  }
}
"""

TRANSACTIONS_QUERY = """
query Tx($first: Int, $after: String, $where: TransactionsWhereInput) {
  findTransactions(first: $first, after: $after, where: $where) {
    edges { node {
      objectId Type Tender Amount
      Order { objectId Total CompletedAt }
    } }
    pageInfo { hasNextPage endCursor }
  }
}
"""

TAX_ITEMS_QUERY = """
query OrderItemsTax($first: Int, $after: String, $where: OrderItemsWhereInput) {
  findOrderItems(first: $first, after: $after, where: $where) {
    edges { node { objectId SoldAt Taxes { ... on Element { value } } } }
    pageInfo { hasNextPage endCursor }
  }
}
"""


@dataclass(frozen=True)
class DailyCloseReport:
    sales_date: date
    timezone_label: str
    order_count: int
    total_collected_cents: int
    subtotal_cents: int
    discounts_cents: int
    taxes_cents: int
    tender_cents: dict[str, int]
    mj_tax_cents: int
    sales_tax_cents: int
    shift_end_local: datetime | None = None
    register_name: str = "Register 1"

    @property
    def mj_oktap_cents(self) -> int:
        return round(self.mj_tax_cents * K_MJ)

    @property
    def sales_oktap_cents(self) -> int:
        return round(self.sales_tax_cents * K_SALES)

    @property
    def total_oktap_cents(self) -> int:
        return self.mj_oktap_cents + self.sales_oktap_cents


def local_day_utc_range(local_day: date, tz: ZoneInfo) -> tuple[str, str]:
    start = datetime(local_day.year, local_day.month, local_day.day, 0, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    end = datetime(local_day.year, local_day.month, local_day.day, 23, 59, 59, 999000, tzinfo=tz).astimezone(
        timezone.utc
    )
    return (
        start.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        end.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    )


def _parse_tax_value(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            v = json.loads(raw)
            return v if isinstance(v, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def build_daily_close_report(
    sales_date: date,
    *,
    credentials_path: str | None,
    tz: ZoneInfo,
    shift_end_local: datetime | None = None,
    register_name: str = "Register 1",
) -> DailyCloseReport:
    from_iso, to_iso = local_day_utc_range(sales_date, tz)
    where = {"CompletedAt": {"greaterThanOrEqualTo": from_iso, "lessThanOrEqualTo": to_iso}}
    orders = fetch_paginated(
        "findOrders",
        ORDERS_QUERY,
        {"first": PAGE_SIZE, "where": where},
        credentials_path=credentials_path,
    )
    order_ids = {str(o.get("objectId")) for o in orders if o.get("objectId")}
    total = subtotal = discounts = taxes = 0
    for o in orders:
        total += int(o.get("Total") or 0)
        subtotal += int(o.get("Subtotal") or 0)
        discounts += int(float(o.get("Discounts") or 0))
        taxes += int(float(o.get("Taxes") or 0))

    txs = fetch_paginated(
        "findTransactions",
        TRANSACTIONS_QUERY,
        {"first": PAGE_SIZE, "where": {"createdAt": {"greaterThanOrEqualTo": from_iso, "lessThanOrEqualTo": to_iso}}},
        credentials_path=credentials_path,
    )
    tender: dict[str, int] = defaultdict(int)
    for tx in txs:
        if str(tx.get("Type") or "").lower() != "sale":
            continue
        order = tx.get("Order") or {}
        if str(order.get("objectId") or "") not in order_ids:
            continue
        label = str(tx.get("Tender") or "unknown").upper()
        tender[label] += int(tx.get("Amount") or 0)

    items = fetch_paginated(
        "findOrderItems",
        TAX_ITEMS_QUERY,
        {"first": PAGE_SIZE, "where": {"SoldAt": {"greaterThanOrEqualTo": from_iso, "lessThanOrEqualTo": to_iso}}},
        credentials_path=credentials_path,
    )
    mj = sales = 0
    seen: set[str] = set()
    for n in items:
        key = order_item_key(n)
        if key in seen:
            continue
        seen.add(key)
        for el in n.get("Taxes") or []:
            val = _parse_tax_value((el or {}).get("value"))
            if not val or val.get("exempt"):
                continue
            cents = int(val.get("taxAmount") or 0)
            tid = str(val.get("taxId") or "")
            name = str(val.get("taxName") or "").upper()
            if tid == MJ_TAX_ID or "CANNABIS" in name:
                mj += cents
            elif tid == SALES_TAX_ID or "SALES" in name:
                sales += cents

    tz_label = getattr(tz, "key", None) or str(tz)
    return DailyCloseReport(
        sales_date=sales_date,
        timezone_label=str(tz_label),
        order_count=len(orders),
        total_collected_cents=total,
        subtotal_cents=subtotal,
        discounts_cents=discounts,
        taxes_cents=taxes,
        tender_cents=dict(sorted(tender.items())),
        mj_tax_cents=mj,
        sales_tax_cents=sales,
        shift_end_local=shift_end_local,
        register_name=register_name,
    )


def format_daily_close_telegram(report: DailyCloseReport) -> str:
    lines = [
        f"NUGZ Daily Close - {report.register_name}",
        f"Date: {report.sales_date.isoformat()} ({report.timezone_label})",
        "",
        f"Total collected: {_money(report.total_collected_cents)}",
    ]
    for tender, cents in sorted(report.tender_cents.items()):
        lines.append(f"  {tender.title()}: {_money(cents)}")
    lines.extend(
        [
            "",
            "Taxes collected (GrowFlow POS)",
            f"  MJ / cannabis: {_money(report.mj_tax_cents)}",
            f"  Sales:         {_money(report.sales_tax_cents)}",
            f"  Total:         {_money(report.mj_tax_cents + report.sales_tax_cents)}",
            "",
            "OKTAP set-aside (April 2026 calibration)",
            f"  MJ / cannabis: {_money(report.mj_oktap_cents)}",
            f"  Sales:         {_money(report.sales_oktap_cents)}",
            f"  TOTAL TO HOLD: {_money(report.total_oktap_cents)}",
            "",
            f"Orders: {report.order_count}",
        ]
    )
    if report.shift_end_local:
        lines.append(f"Register closed: {report.shift_end_local.strftime('%I:%M %p').lstrip('0')} local")
    return "\n".join(lines)
