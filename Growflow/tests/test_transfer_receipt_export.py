"""Unit tests for transfer receipt flattening (no API)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from zoneinfo import ZoneInfo

from lib.transfer_receipt_export import (
    fetch_transfer_nodes,
    fetch_transfer_receipt_rows,
    parse_received_at_utc,
    rows_from_transfer_node,
)


def test_rows_from_transfer_node_timestamps():
    node = {
        "objectId": "T1",
        "Status": "Accepted",
        "ReceivedAt": "2026-04-14T20:03:49.000Z",
        "createdAt": "x",
        "updatedAt": "y",
        "FromName": "Vendor LLC",
        "Store": {"objectId": "S1", "Name": "Nugz Dispensary"},
        "ReceivingStore": None,
        "Packages": [
            {
                "objectId": "P1",
                "SKU": "111",
                "OriginalQty": 4,
                "CurrentQty": 4,
                "Cost": 1200,
                "Product": {
                    "objectId": "PR1",
                    "Name": "Widget",
                    "SKU": None,
                    "Brand": {"Name": "BrandA"},
                },
            }
        ],
    }
    exp = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
    rows = rows_from_transfer_node(
        node,
        org_slug="testorg",
        exported_at=exp,
        store_tz=ZoneInfo("America/Chicago"),
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["transfer_object_id"] == "T1"
    recv = parse_received_at_utc("2026-04-14T20:03:49.000Z")
    assert recv and r["received_at_epoch_ms"] == int(recv.timestamp() * 1000)
    assert r["received_date_local"] == "2026-04-14"
    assert r["product_object_id"] == "PR1"
    assert r["original_qty"] == 4
    assert r["cost_cents"] == 1200


@patch("lib.transfer_receipt_export.fetch_transfer_nodes")
def test_fetch_transfer_receipt_rows_skip(mock_nodes):
    """skip=1, first=1 uses the second transfer node only."""
    mock_nodes.return_value = [
        {
            "objectId": "OLD",
            "Status": "Accepted",
            "ReceivedAt": "2026-01-01T00:00:00.000Z",
            "createdAt": "c",
            "updatedAt": "u",
            "FromName": "A",
            "Store": {"objectId": "s", "Name": "Store"},
            "ReceivingStore": None,
            "Packages": [],
        },
        {
            "objectId": "NEW",
            "Status": "Accepted",
            "ReceivedAt": "2026-01-02T00:00:00.000Z",
            "createdAt": "c",
            "updatedAt": "u",
            "FromName": "B",
            "Store": {"objectId": "s", "Name": "Store"},
            "ReceivingStore": None,
            "Packages": [
                {
                    "objectId": "p1",
                    "SKU": "1",
                    "OriginalQty": 2,
                    "CurrentQty": 2,
                    "Cost": 100,
                    "Product": {"objectId": "pr", "Name": "X", "SKU": None, "Brand": {"Name": "Y"}},
                }
            ],
        },
    ]
    rows = fetch_transfer_receipt_rows(first=1, skip=1, status="Accepted", credentials_path=None)
    mock_nodes.assert_called_once_with(first=2, status="Accepted", credentials_path=None)
    assert len(rows) == 1
    assert rows[0]["transfer_object_id"] == "NEW"


def test_fetch_transfer_nodes_paginates_until_requested_count(monkeypatch):
    calls = []
    pages = [
        {
            "data": {
                "findTransfers": {
                    "edges": [{"node": {"objectId": "T1"}}],
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                }
            }
        },
        {
            "data": {
                "findTransfers": {
                    "edges": [{"node": {"objectId": "T2"}}],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        },
    ]

    def fake_graphql_request(query, variables, credentials_path=None):
        calls.append(variables)
        return pages[len(calls) - 1]

    monkeypatch.setattr("lib.transfer_receipt_export.graphql_request", fake_graphql_request)

    nodes = fetch_transfer_nodes(first=2, status="Accepted", credentials_path="creds.json")

    assert [n["objectId"] for n in nodes] == ["T1", "T2"]
    assert calls == [
        {"first": 2, "after": None, "where": {"Status": {"equalTo": "Accepted"}}},
        {"first": 1, "after": "cursor-1", "where": {"Status": {"equalTo": "Accepted"}}},
    ]
