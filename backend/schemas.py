"""Pydantic schemas for bill extraction, human review, and proportional splitting."""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    """Represents an individual item parsed from a receipt."""
    item_name: str = Field(..., description="Name or description of the purchased item")
    quantity: float = Field(default=1.0, ge=0.0, description="Quantity purchased")
    price: float = Field(..., ge=0.0, description="Total price for this line item (quantity * unit price)")


class ReceiptExtractionResult(BaseModel):
    """Structured extraction output from multimodal Gemini Vision model."""
    merchant_name: str = Field(default="Unknown Merchant", description="Business or restaurant name")
    line_items: List[LineItem] = Field(default_factory=list, description="Extracted line items")
    subtotal: float = Field(default=0.0, ge=0.0, description="Sum of line items before tax/fees")
    taxes: float = Field(default=0.0, ge=0.0, description="Total sales tax / VAT / GST")
    service_charge: float = Field(default=0.0, ge=0.0, description="Mandatory service fee or tip")
    discounts: float = Field(default=0.0, ge=0.0, description="Any promotional deductions / discounts")
    grand_total: float = Field(default=0.0, ge=0.0, description="Final payable amount on the receipt")
    field_confidence: Dict[str, float] = Field(
        default_factory=lambda: {
            "merchant_name": 0.95,
            "line_items": 0.90,
            "subtotal": 0.92,
            "taxes": 0.88,
            "service_charge": 0.90,
            "discounts": 0.95,
            "grand_total": 0.96,
        },
        description="Confidence score (0.0 to 1.0) per extracted field"
    )
    currency: str = Field(default="$", description="Detected currency symbol or ISO code")
    math_mismatch_warning: bool = Field(
        default=False,
        description="Flag set to true if item sum != subtotal or calculated total != grand_total"
    )
    mismatch_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Detailed diagnostics on mathematical discrepancies"
    )


class Participant(BaseModel):
    """Represents an individual participating in the bill split."""
    id: str = Field(..., description="Unique ID of participant")
    name: str = Field(..., description="Display name of participant")
    color: Optional[str] = Field(default=None, description="Hex color or theme for avatar UI")


class ItemAssignment(BaseModel):
    """Mapping of an item index to assigned participant IDs."""
    item_index: int = Field(..., ge=0, description="Zero-based index of item in line_items")
    assigned_participant_ids: List[str] = Field(
        default_factory=list,
        description="List of participant IDs sharing this item. If empty, considered unassigned."
    )


class SplitRequest(BaseModel):
    """Payload sent from frontend to calculate proportional bill split."""
    receipt_data: ReceiptExtractionResult
    participants: List[Participant]
    assignments: List[ItemAssignment]


class ConsumedItemDetail(BaseModel):
    """Details of an item consumed by a participant with their proportional fraction."""
    item_name: str
    original_price: float
    split_count: int
    individual_share: float


class ParticipantShare(BaseModel):
    """Breakdown of an individual participant's share of the bill."""
    participant_id: str
    name: str
    items_consumed: List[ConsumedItemDetail]
    food_subtotal: float = Field(..., description="Raw food cost consumed by this individual")
    proportional_fee_share: float = Field(
        ...,
        description="Net tax + service - discount share proportional to food consumed"
    )
    tax_share: float = Field(default=0.0, description="Proportional tax component")
    service_charge_share: float = Field(default=0.0, description="Proportional service charge component")
    discount_share: float = Field(default=0.0, description="Proportional discount component")
    final_total: float = Field(..., description="Final payable amount (food_subtotal + fee_share)")


class SplitResponse(BaseModel):
    """Final calculated bill split response."""
    shares: List[ParticipantShare]
    unassigned_items: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Line items that were not assigned to anyone"
    )
    receipt_grand_total: float
    calculated_grand_total: float
    is_balanced: bool = Field(..., description="True if sum of shares exactly equals grand total")
    penny_adjustment: float = Field(
        default=0.0,
        description="Rounding penny adjustment made during cent-balancing"
    )
    total_food_subtotal: float
    total_net_fees: float
