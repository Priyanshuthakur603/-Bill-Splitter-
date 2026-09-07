"""Mathematical Engine for Proportional Bill Splitting & Cent Reconciliation.

Implements proportional tax/fee distribution based strictly on raw food subtotal consumed,
plus the Largest Remainder Method (Hare-Niemeyer) for zero-penny-loss exact reconciliation.
"""
from typing import List, Dict, Tuple, Any
import math
from backend.schemas import (
    ReceiptExtractionResult,
    Participant,
    ItemAssignment,
    ParticipantShare,
    ConsumedItemDetail,
    SplitResponse,
)


def validate_receipt_math(receipt: ReceiptExtractionResult) -> Tuple[bool, Dict[str, Any]]:
    """Validates receipt arithmetic and flags mismatches with detailed diagnostics.
    
    Checks:
    1. sum(line_items.price) vs subtotal
    2. subtotal + taxes + service_charge - discounts vs grand_total
    """
    items_sum = round(sum(item.price for item in receipt.line_items), 2)
    expected_grand_total = round(
        receipt.subtotal + receipt.taxes + receipt.service_charge - receipt.discounts, 2
    )

    item_subtotal_diff = round(abs(items_sum - receipt.subtotal), 2)
    grand_total_diff = round(abs(expected_grand_total - receipt.grand_total), 2)

    has_mismatch = (item_subtotal_diff > 0.05) or (grand_total_diff > 0.05)

    details = {
        "items_sum": items_sum,
        "printed_subtotal": receipt.subtotal,
        "item_subtotal_diff": item_subtotal_diff,
        "expected_grand_total": expected_grand_total,
        "printed_grand_total": receipt.grand_total,
        "grand_total_diff": grand_total_diff,
        "item_sum_matches_subtotal": item_subtotal_diff <= 0.05,
        "components_match_grand_total": grand_total_diff <= 0.05,
    }

    return has_mismatch, details


def compute_proportional_split(
    receipt: ReceiptExtractionResult,
    participants: List[Participant],
    assignments: List[ItemAssignment],
) -> SplitResponse:
    """Computes mathematically correct proportional bill split across participants.
    
    Formula:
        Person i Fee Share = Total Net Fees * (Person i Food Subtotal / Receipt Food Subtotal)
        Person i Final Total = Person i Food Subtotal + Person i Fee Share
    
    Reconciliation:
        Uses the Largest Remainder (Hare-Niemeyer) algorithm so that:
        sum(Person i Final Total) == Target Total (exact cent balance down to the penny).
    """
    if not participants:
        raise ValueError("At least one participant is required to split the bill.")

    participant_dict: Dict[str, Participant] = {p.id: p for p in participants}
    participant_food: Dict[str, float] = {p.id: 0.0 for p in participants}
    participant_items: Dict[str, List[ConsumedItemDetail]] = {p.id: [] for p in participants}

    # Map item assignments
    assignment_map: Dict[int, List[str]] = {}
    for a in assignments:
        assignment_map[a.item_index] = a.assigned_participant_ids

    unassigned_items: List[Dict[str, Any]] = []

    # Calculate individual food consumption for each item
    for idx, item in enumerate(receipt.line_items):
        assigned_ids = assignment_map.get(idx, [])
        valid_assigned = [pid for pid in assigned_ids if pid in participant_dict]

        if not valid_assigned:
            unassigned_items.append({
                "item_index": idx,
                "item_name": item.item_name,
                "price": item.price,
                "quantity": item.quantity,
            })
            continue

        share_count = len(valid_assigned)
        individual_item_cost = item.price / share_count

        for pid in valid_assigned:
            participant_food[pid] += individual_item_cost
            participant_items[pid].append(
                ConsumedItemDetail(
                    item_name=item.item_name,
                    original_price=item.price,
                    split_count=share_count,
                    individual_share=round(individual_item_cost, 4),
                )
            )

    total_assigned_food = sum(participant_food.values())
    total_unassigned_food = sum(item["price"] for item in unassigned_items)
    total_items_food = total_assigned_food + total_unassigned_food

    # Base subtotal for proportion calculation
    denominator_subtotal = total_assigned_food if total_assigned_food > 0 else (
        receipt.subtotal if receipt.subtotal > 0 else total_items_food
    )

    total_net_fees = round(receipt.taxes + receipt.service_charge - receipt.discounts, 2)
    
    # If unassigned items exist, participants only cover their proportional share of total fees
    if total_items_food > 0 and len(unassigned_items) > 0:
        assignment_ratio = total_assigned_food / total_items_food
    else:
        assignment_ratio = 1.0

    effective_net_fees = total_net_fees * assignment_ratio
    effective_taxes = receipt.taxes * assignment_ratio
    effective_service = receipt.service_charge * assignment_ratio
    effective_discounts = receipt.discounts * assignment_ratio

    # Check if receipt has a printed arithmetic mismatch
    has_mismatch, _ = validate_receipt_math(receipt)

    # When all items are assigned and no unassigned items exist:
    # Target is receipt.grand_total (or assigned fraction thereof)
    if len(unassigned_items) == 0:
        grand_target = receipt.grand_total
    else:
        grand_target = round(total_assigned_food + effective_net_fees, 2)

    exact_shares: List[Dict[str, Any]] = []

    for p in participants:
        food = participant_food[p.id]

        if denominator_subtotal > 0:
            ratio = food / denominator_subtotal
            proportional_fee = effective_net_fees * ratio
            tax_share = effective_taxes * ratio
            svc_share = effective_service * ratio
            disc_share = effective_discounts * ratio
            
            # If all items are assigned and there was an uncorrected printed discrepancy in receipt.grand_total,
            # scale exact final proportionally to match receipt.grand_total
            if len(unassigned_items) == 0 and abs((total_assigned_food + effective_net_fees) - receipt.grand_total) > 0.05:
                # Distribute the full printed grand total in exact proportion to consumed food
                exact_final = receipt.grand_total * ratio
                proportional_fee = exact_final - food
            else:
                exact_final = food + proportional_fee
        else:
            # Edge Case: Zero food subtotal (e.g. only cover fee or room charge)
            ratio = 1.0 / len(participants)
            exact_final = grand_target * ratio
            proportional_fee = exact_final
            tax_share = effective_taxes * ratio
            svc_share = effective_service * ratio
            disc_share = effective_discounts * ratio

        exact_shares.append({
            "participant_id": p.id,
            "name": p.name,
            "items_consumed": participant_items[p.id],
            "food_subtotal": food,
            "proportional_fee_share": proportional_fee,
            "tax_share": tax_share,
            "service_charge_share": svc_share,
            "discount_share": disc_share,
            "exact_final": exact_final,
        })

    # Cent balancing via Largest Remainder Method (Hare-Niemeyer)
    target_cents = round(grand_target * 100)

    for s in exact_shares:
        cents_float = s["exact_final"] * 100
        cents_floor = math.floor(cents_float)
        s["cents_floor"] = cents_floor
        s["cents_remainder"] = cents_float - cents_floor
        s["final_cents"] = cents_floor

    allocated_cents = sum(s["final_cents"] for s in exact_shares)
    diff_cents = target_cents - allocated_cents

    # Allocate residual cents (usually 0, +1, or +2)
    if diff_cents > 0:
        sorted_indices = sorted(
            range(len(exact_shares)),
            key=lambda i: exact_shares[i]["cents_remainder"],
            reverse=True,
        )
        for i in range(min(diff_cents, len(sorted_indices))):
            exact_shares[sorted_indices[i]]["final_cents"] += 1
    elif diff_cents < 0:
        sorted_indices = sorted(
            range(len(exact_shares)),
            key=lambda i: exact_shares[i]["cents_remainder"],
        )
        for i in range(min(abs(diff_cents), len(sorted_indices))):
            exact_shares[sorted_indices[i]]["final_cents"] -= 1

    # Format final participant shares
    result_shares: List[ParticipantShare] = []
    for s in exact_shares:
        final_amt = round(s["final_cents"] / 100.0, 2)
        food_rounded = round(s["food_subtotal"], 2)
        fee_share_rounded = round(final_amt - food_rounded, 2)

        result_shares.append(
            ParticipantShare(
                participant_id=s["participant_id"],
                name=s["name"],
                items_consumed=s["items_consumed"],
                food_subtotal=food_rounded,
                proportional_fee_share=fee_share_rounded,
                tax_share=round(s["tax_share"], 2),
                service_charge_share=round(s["service_charge_share"], 2),
                discount_share=round(s["discount_share"], 2),
                final_total=final_amt,
            )
        )

    calculated_total = round(sum(s.final_total for s in result_shares), 2)
    is_balanced = abs(calculated_total - grand_target) < 0.001
    penny_adj = round(calculated_total - sum(s["exact_final"] for s in exact_shares), 4)

    return SplitResponse(
        shares=result_shares,
        unassigned_items=unassigned_items,
        receipt_grand_total=grand_target,
        calculated_grand_total=calculated_total,
        is_balanced=is_balanced,
        penny_adjustment=penny_adj,
        total_food_subtotal=round(total_assigned_food, 2),
        total_net_fees=round(effective_net_fees, 2),
    )
