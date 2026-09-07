"""Automated unit tests for proportional bill splitting and mathematical precision."""
import json
import os
import pytest
from backend.schemas import (
    ReceiptExtractionResult,
    LineItem,
    Participant,
    ItemAssignment,
)
from backend.math_engine import compute_proportional_split, validate_receipt_math


MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "edge_case_manifest.json")


@pytest.fixture
def manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_proportional_tax_fairness():
    """Verify that an individual ordering expensive items pays proportionally higher tax

    than someone ordering cheap items, rather than splitting taxes 50/50.
    """
    receipt = ReceiptExtractionResult(
        merchant_name="Fairness Grill",
        line_items=[
            LineItem(item_name="Cheap Snack", quantity=1, price=10.00),
            LineItem(item_name="Expensive Wine", quantity=1, price=90.00),
        ],
        subtotal=100.00,
        taxes=10.00,  # 10% tax
        service_charge=0.0,
        discounts=0.0,
        grand_total=110.00,
    )
    p1 = Participant(id="p1", name="Cheap Person")
    p2 = Participant(id="p2", name="Expensive Person")

    assignments = [
        ItemAssignment(item_index=0, assigned_participant_ids=["p1"]),
        ItemAssignment(item_index=1, assigned_participant_ids=["p2"]),
    ]

    res = compute_proportional_split(receipt, [p1, p2], assignments)

    share_p1 = next(s for s in res.shares if s.participant_id == "p1")
    share_p2 = next(s for s in res.shares if s.participant_id == "p2")

    # Person 1 consumed 10% of food ($10 of $100), so must pay exactly 10% of tax ($1.00)
    assert share_p1.food_subtotal == 10.00
    assert share_p1.proportional_fee_share == 1.00
    assert share_p1.final_total == 11.00

    # Person 2 consumed 90% of food ($90 of $100), so must pay exactly 90% of tax ($9.00)
    assert share_p2.food_subtotal == 90.00
    assert share_p2.proportional_fee_share == 9.00
    assert share_p2.final_total == 99.00

    # Sum must equal exact grand total
    assert res.calculated_grand_total == 110.00
    assert res.is_balanced is True


def test_three_way_penny_balancing():
    """Test Hare-Niemeyer cent balancing for a 3-way split of $10.00.

    10 / 3 = 3.3333. Base floor is 3.33 * 3 = 9.99.
    The algorithm must award the remaining 1 cent to ensure exact $10.00 balance.
    """
    receipt = ReceiptExtractionResult(
        merchant_name="Penny Test",
        line_items=[
            LineItem(item_name="Shared Dish", quantity=1, price=10.00),
        ],
        subtotal=10.00,
        taxes=0.0,
        service_charge=0.0,
        discounts=0.0,
        grand_total=10.00,
    )
    participants = [
        Participant(id="p1", name="Alice"),
        Participant(id="p2", name="Bob"),
        Participant(id="p3", name="Charlie"),
    ]
    assignments = [
        ItemAssignment(item_index=0, assigned_participant_ids=["p1", "p2", "p3"])
    ]

    res = compute_proportional_split(receipt, participants, assignments)
    totals = [s.final_total for s in res.shares]

    # Two participants pay 3.33, one participant gets the remainder cent and pays 3.34
    assert sorted(totals) == [3.33, 3.33, 3.34]
    assert sum(totals) == 10.00
    assert res.is_balanced is True


def test_math_mismatch_detection(manifest):
    """Verify detection of printed register arithmetic errors (Edge Case 3)."""
    case3 = manifest["3_incorrect_printed_math"]["ground_truth"]
    receipt = ReceiptExtractionResult(
        merchant_name=case3["merchant_name"],
        line_items=[LineItem(**it) for it in case3["line_items"]],
        subtotal=case3["subtotal"],
        taxes=case3["taxes"],
        service_charge=case3["service_charge"],
        discounts=case3["discounts"],
        grand_total=case3["grand_total"],
    )

    has_mismatch, details = validate_receipt_math(receipt)
    assert has_mismatch is True
    assert details["items_sum"] == 38.00
    assert details["printed_subtotal"] == 42.00
    assert details["item_subtotal_diff"] == 4.00
    assert details["item_sum_matches_subtotal"] is False


def test_heavy_discounts_proportional_reduction(manifest):
    """Verify that promotional discounts reduce fees/total proportionally (Edge Case 4)."""
    case4 = manifest["4_heavy_discounts"]["ground_truth"]
    receipt = ReceiptExtractionResult(
        merchant_name=case4["merchant_name"],
        line_items=[LineItem(**it) for it in case4["line_items"]],
        subtotal=case4["subtotal"],
        taxes=case4["taxes"],
        service_charge=case4["service_charge"],
        discounts=case4["discounts"],
        grand_total=case4["grand_total"],
    )

    p1 = Participant(id="p1", name="Sashimi Eater")
    p2 = Participant(id="p2", name="Wagyu Eater")

    assignments = [
        ItemAssignment(item_index=0, assigned_participant_ids=["p1"]),  # 65.00
        ItemAssignment(item_index=1, assigned_participant_ids=["p2"]),  # 48.00
        ItemAssignment(item_index=2, assigned_participant_ids=["p1", "p2"]),  # 8.00
        ItemAssignment(item_index=3, assigned_participant_ids=["p1", "p2"]),  # 24.00
    ]

    res = compute_proportional_split(receipt, [p1, p2], assignments)
    assert res.is_balanced is True
    assert res.calculated_grand_total == case4["grand_total"]
    assert res.total_net_fees == round(case4["taxes"] + case4["service_charge"] - case4["discounts"], 2)


def test_zero_food_subtotal_fallback(manifest):
    """Verify graceful handling when receipt food subtotal is 0 (Edge Case 12)."""
    case12 = manifest["12_zero_food_subtotal"]["ground_truth"]
    receipt = ReceiptExtractionResult(
        merchant_name=case12["merchant_name"],
        line_items=[LineItem(**it) for it in case12["line_items"]],
        subtotal=case12["subtotal"],
        taxes=case12["taxes"],
        service_charge=case12["service_charge"],
        discounts=case12["discounts"],
        grand_total=case12["grand_total"],
    )

    p1 = Participant(id="p1", name="Guest 1")
    p2 = Participant(id="p2", name="Guest 2")

    assignments = [
        ItemAssignment(item_index=0, assigned_participant_ids=["p1", "p2"])
    ]

    res = compute_proportional_split(receipt, [p1, p2], assignments)
    assert res.is_balanced is True
    assert res.calculated_grand_total == 55.00
    # $55.00 split 2 ways is 27.50 each
    assert res.shares[0].final_total == 27.50
    assert res.shares[1].final_total == 27.50


def test_all_12_manifest_edge_cases_balance(manifest):
    """Iterate through all 12 edge cases and verify that split sum strictly equals grand total."""
    for case_id, case_info in manifest.items():
        gt = case_info["ground_truth"]
        receipt = ReceiptExtractionResult(
            merchant_name=gt["merchant_name"],
            line_items=[LineItem(**it) for it in gt["line_items"]],
            subtotal=gt["subtotal"],
            taxes=gt["taxes"],
            service_charge=gt["service_charge"],
            discounts=gt["discounts"],
            grand_total=gt["grand_total"],
        )

        p1 = Participant(id="p1", name="Priya")
        p2 = Participant(id="p2", name="Rahul")
        p3 = Participant(id="p3", name="Amit")
        participants = [p1, p2, p3]

        # Assign items across participants
        assignments = []
        for idx, _ in enumerate(receipt.line_items):
            if idx % 3 == 0:
                assignments.append(ItemAssignment(item_index=idx, assigned_participant_ids=["p1"]))
            elif idx % 3 == 1:
                assignments.append(ItemAssignment(item_index=idx, assigned_participant_ids=["p2", "p3"]))
            else:
                assignments.append(ItemAssignment(item_index=idx, assigned_participant_ids=["p1", "p2", "p3"]))

        res = compute_proportional_split(receipt, participants, assignments)

        # MANDATORY: Sum of all individual final amounts strictly equals the total grand total of the receipt
        assert res.is_balanced is True, f"Failed cent balance on edge case {case_id}"
        assert abs(res.calculated_grand_total - gt["grand_total"]) < 0.001, (
            f"Discrepancy on {case_id}: calc={res.calculated_grand_total}, target={gt['grand_total']}"
        )
