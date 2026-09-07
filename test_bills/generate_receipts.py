"""Generate 12 realistic receipt images and ground-truth metadata for edge-case testing."""
import os
import json
import math
import random
from typing import Dict, Any, List
from PIL import Image, ImageDraw, ImageFont, ImageFilter


RECEIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(RECEIPTS_DIR, "edge_case_manifest.json")


def get_default_font(size: int = 18):
    """Attempt to load a monospaced or standard truetype font, fallback to default."""
    font_candidates = [
        "consola.ttf", "arial.ttf", "cour.ttf", "DejaVuSansMono.ttf"
    ]
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def get_bold_font(size: int = 20):
    font_candidates = [
        "consolab.ttf", "arialbd.ttf", "courbd.ttf"
    ]
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    return get_default_font(size)


def create_receipt_image(
    filename: str,
    merchant: str,
    items: List[Dict[str, Any]],
    subtotal: float,
    taxes: float,
    service_charge: float,
    discounts: float,
    grand_total: float,
    currency: str = "$",
    extra_text: List[str] = None,
    faded: bool = False,
    crumpled: bool = False,
    angled: bool = False,
    handwritten_note: str = None,
) -> str:
    """Renders a realistic receipt image using PIL and applies visual effects."""
    width, height = 480, 720
    bg_color = (250, 248, 242) if not crumpled else (238, 234, 224)
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    font_title = get_bold_font(22)
    font_sub = get_default_font(15)
    font_body = get_default_font(16)
    font_bold = get_bold_font(17)

    text_color = (20, 20, 20) if not faded else (135, 135, 135)
    line_color = (180, 180, 180) if not faded else (220, 220, 220)

    y = 30
    # Header
    draw.text((width // 2, y), merchant.upper(), font=font_title, fill=text_color, anchor="mt")
    y += 32
    draw.text((width // 2, y), "123 Culinary Boulevard, Suite 400", font=font_sub, fill=text_color, anchor="mt")
    y += 22
    draw.text((width // 2, y), "Tel: +1 (555) 019-2831", font=font_sub, fill=text_color, anchor="mt")
    y += 24
    draw.text((width // 2, y), "Date: 2026-09-07  Time: 20:45", font=font_sub, fill=text_color, anchor="mt")
    y += 26

    # Divider
    draw.line([(30, y), (width - 30, y)], fill=line_color, width=2)
    y += 15

    # Column headers
    draw.text((35, y), "ITEM", font=font_bold, fill=text_color)
    draw.text((280, y), "QTY", font=font_bold, fill=text_color)
    draw.text((width - 35, y), "AMT", font=font_bold, fill=text_color, anchor="rt")
    y += 24
    draw.line([(30, y), (width - 30, y)], fill=line_color, width=1)
    y += 12

    # Items
    for it in items:
        name = it["item_name"]
        qty = f"{it['quantity']:g}"
        amt = f"{currency}{it['price']:.2f}"
        draw.text((35, y), name[:22], font=font_body, fill=text_color)
        draw.text((290, y), qty, font=font_body, fill=text_color)
        draw.text((width - 35, y), amt, font=font_body, fill=text_color, anchor="rt")
        y += 24

    y += 8
    draw.line([(30, y), (width - 30, y)], fill=line_color, width=1)
    y += 14

    # Summary
    def draw_summary_line(label: str, val: float, is_negative=False, is_bold=False):
        nonlocal y
        f = font_bold if is_bold else font_body
        prefix = "-" if is_negative else ""
        text_val = f"{prefix}{currency}{abs(val):.2f}"
        draw.text((200, y), label, font=f, fill=text_color)
        draw.text((width - 35, y), text_val, font=f, fill=text_color, anchor="rt")
        y += 24

    draw_summary_line("Subtotal:", subtotal)
    if discounts > 0:
        draw_summary_line("Discounts:", discounts, is_negative=True)
    if taxes > 0:
        draw_summary_line("Tax (Sales/VAT):", taxes)
    if service_charge > 0:
        draw_summary_line("Service Charge:", service_charge)

    y += 6
    draw.line([(180, y), (width - 30, y)], fill=line_color, width=2)
    y += 12
    draw_summary_line("GRAND TOTAL:", grand_total, is_bold=True)

    # Extra annotations / footer
    y += 14
    if extra_text:
        for line in extra_text:
            draw.text((width // 2, y), line, font=font_sub, fill=text_color, anchor="mt")
            y += 18

    # Handwritten tip note
    if handwritten_note:
        y += 10
        draw.text(
            (50, y),
            handwritten_note,
            font=font_bold,
            fill=(20, 50, 160),  # Blue pen color
        )

    # Visual degradations
    if faded:
        # Lower contrast and add noise
        img = img.filter(ImageFilter.BoxBlur(0.6))

    if crumpled:
        # Draw crease lines
        for _ in range(8):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            draw.line([(x1, y1), (x2, y2)], fill=(190, 185, 175), width=2)
        img = img.filter(ImageFilter.GaussianBlur(0.4))

    if angled:
        # Rotate image slightly with expansion
        img = img.rotate(6, expand=True, fillcolor=(240, 240, 240), resample=Image.BICUBIC)

    file_path = os.path.join(RECEIPTS_DIR, filename)
    img.save(file_path, quality=92)
    return file_path


def generate_all_12_edge_cases():
    """Generates all 12 edge cases required by the specification."""
    edge_cases = [
        {
            "id": "1_crumpled_paper",
            "name": "Crumpled Paper Receipt",
            "description": "Degraded, folded receipt paper with wrinkles and shadows affecting OCR clarity.",
            "merchant_name": "The Bistro Garden",
            "currency": "$",
            "items": [
                {"item_name": "Truffle Fries", "quantity": 1, "price": 14.50},
                {"item_name": "Steak Frites", "quantity": 2, "price": 56.00},
                {"item_name": "Sparkling Water", "quantity": 2, "price": 9.00},
            ],
            "subtotal": 79.50,
            "taxes": 7.16,
            "service_charge": 7.95,
            "discounts": 0.0,
            "grand_total": 94.61,
            "confidence": {"merchant_name": 0.85, "line_items": 0.76, "subtotal": 0.78, "taxes": 0.74, "grand_total": 0.82},
            "faded": False,
            "crumpled": True,
            "angled": False,
        },
        {
            "id": "2_angled_shot",
            "name": "Angled Perspective Shot",
            "description": "Camera photo taken at an angle with tilted perspective distortion.",
            "merchant_name": "Trattoria Romana",
            "currency": "$",
            "items": [
                {"item_name": "Bruschetta Trio", "quantity": 1, "price": 12.00},
                {"item_name": "Pappardelle Ragu", "quantity": 2, "price": 44.00},
                {"item_name": "Chianti Classico", "quantity": 1, "price": 38.00},
                {"item_name": "Tiramisu", "quantity": 1, "price": 11.00},
            ],
            "subtotal": 105.00,
            "taxes": 9.45,
            "service_charge": 10.50,
            "discounts": 0.0,
            "grand_total": 124.95,
            "confidence": {"merchant_name": 0.82, "line_items": 0.74, "subtotal": 0.79, "taxes": 0.80, "grand_total": 0.84},
            "faded": False,
            "crumpled": False,
            "angled": True,
        },
        {
            "id": "3_incorrect_printed_math",
            "name": "Incorrect Printed Math (Mismatch)",
            "description": "Register error where printed items sum to $38.00 but printed subtotal is erroneously printed as $42.00.",
            "merchant_name": "Retro Diner Cafe",
            "currency": "$",
            "items": [
                {"item_name": "Classic Burger", "quantity": 1, "price": 15.00},
                {"item_name": "Curly Fries", "quantity": 1, "price": 6.00},
                {"item_name": "Vanilla Shake", "quantity": 1, "price": 7.00},
                {"item_name": "Hot Dog", "quantity": 1, "price": 10.00},
            ],
            "subtotal": 42.00,  # Intentional discrepancy! Sum is 38.00
            "taxes": 3.78,
            "service_charge": 0.0,
            "discounts": 0.0,
            "grand_total": 45.78,
            "confidence": {"merchant_name": 0.95, "line_items": 0.92, "subtotal": 0.65, "taxes": 0.90, "grand_total": 0.88},
            "faded": False,
            "crumpled": False,
            "angled": False,
            "extra_text": ["* REGISTER SYNC WARNING *"],
        },
        {
            "id": "4_heavy_discounts",
            "name": "Heavy Discounts & Promo Vouchers",
            "description": "Bill with substantial promotional discount (-$35.00) that must proportionally reduce participant shares.",
            "merchant_name": "Sake & Robata Grill",
            "currency": "$",
            "items": [
                {"item_name": "Sashimi Platter", "quantity": 1, "price": 65.00},
                {"item_name": "Wagyu Skewers", "quantity": 2, "price": 48.00},
                {"item_name": "Edamame", "quantity": 1, "price": 8.00},
                {"item_name": "Hot Sake Carafe", "quantity": 2, "price": 24.00},
            ],
            "subtotal": 145.00,
            "taxes": 9.90,
            "service_charge": 11.00,
            "discounts": 35.00,
            "grand_total": 130.90,
            "confidence": {"merchant_name": 0.96, "line_items": 0.94, "subtotal": 0.95, "taxes": 0.92, "discounts": 0.94, "grand_total": 0.96},
            "faded": False,
            "crumpled": False,
            "angled": False,
            "extra_text": ["PROMO CODE: VIPHAPPYHOUR (-$35)"],
        },
        {
            "id": "5_zero_tax_service_only",
            "name": "Zero Tax (Service Charge Only)",
            "description": "Duty-free / tax-exempt transaction containing 0% sales tax but a 12% mandatory service charge.",
            "merchant_name": "Skyline Lounge (Tax-Free)",
            "currency": "$",
            "items": [
                {"item_name": "Cocktail Old Fashioned", "quantity": 2, "price": 36.00},
                {"item_name": "Artisan Cheese Plate", "quantity": 1, "price": 24.00},
                {"item_name": "Sparkling Wine", "quantity": 1, "price": 40.00},
            ],
            "subtotal": 100.00,
            "taxes": 0.0,
            "service_charge": 12.00,
            "discounts": 0.0,
            "grand_total": 112.00,
            "confidence": {"merchant_name": 0.95, "line_items": 0.95, "subtotal": 0.95, "taxes": 0.98, "service_charge": 0.94, "grand_total": 0.97},
            "faded": False,
            "crumpled": False,
            "angled": False,
        },
        {
            "id": "6_high_tax_multiple_rates",
            "name": "High Tax & Compound Rates",
            "description": "Receipt with composite tax breakdown (State 6.25% + Local Meal Tax 2.75% = 9.0% total).",
            "merchant_name": "Boston Seafood Pier",
            "currency": "$",
            "items": [
                {"item_name": "Lobster Roll Combo", "quantity": 2, "price": 68.00},
                {"item_name": "Clam Chowder Bowl", "quantity": 2, "price": 22.00},
                {"item_name": "Local Craft IPA", "quantity": 3, "price": 27.00},
            ],
            "subtotal": 117.00,
            "taxes": 10.53,  # 9% tax
            "service_charge": 5.00,
            "discounts": 0.0,
            "grand_total": 132.53,
            "confidence": {"merchant_name": 0.94, "line_items": 0.92, "subtotal": 0.93, "taxes": 0.91, "grand_total": 0.95},
            "faded": False,
            "crumpled": False,
            "angled": False,
            "extra_text": ["State Tax: 6.25% | Meal Tax: 2.75%"],
        },
        {
            "id": "7_multi_person_penny_rounding",
            "name": "Multi-Person Penny Rounding (Hare-Niemeyer)",
            "description": "$10.00 split 3 ways yields $3.3333. Hare-Niemeyer cent balancing allocates the extra 1 cent without loss.",
            "merchant_name": "Three Friends Pizzeria",
            "currency": "$",
            "items": [
                {"item_name": "Margherita Pizza", "quantity": 1, "price": 10.00},
                {"item_name": "Garlic Bread", "quantity": 1, "price": 5.00},
                {"item_name": "Soda Can", "quantity": 3, "price": 6.00},
            ],
            "subtotal": 21.00,
            "taxes": 1.89,
            "service_charge": 0.0,
            "discounts": 0.0,
            "grand_total": 22.89,
            "confidence": {"merchant_name": 0.97, "line_items": 0.95, "subtotal": 0.96, "taxes": 0.94, "grand_total": 0.98},
            "faded": False,
            "crumpled": False,
            "angled": False,
        },
        {
            "id": "8_foreign_currency_symbols",
            "name": "Foreign Currency (EUR / INR)",
            "description": "International receipt formatted in Euros (€) with European decimal formatting.",
            "merchant_name": "Brasserie Parisienne",
            "currency": "€",
            "items": [
                {"item_name": "Croissant & Cafe", "quantity": 2, "price": 8.50},
                {"item_name": "Quiche Lorraine", "quantity": 2, "price": 24.00},
                {"item_name": "Bordeaux Rouge", "quantity": 1, "price": 32.00},
            ],
            "subtotal": 64.50,
            "taxes": 6.45,  # 10% TVA
            "service_charge": 0.0,
            "discounts": 0.0,
            "grand_total": 70.95,
            "confidence": {"merchant_name": 0.92, "line_items": 0.90, "subtotal": 0.91, "taxes": 0.89, "grand_total": 0.94},
            "faded": False,
            "crumpled": False,
            "angled": False,
            "extra_text": ["TVA incluse (10%)"],
        },
        {
            "id": "9_handwritten_additions",
            "name": "Handwritten Tip Addition",
            "description": "Receipt with printed total of $55.00 and customer handwritten pen tip of $10.00 making grand total $65.00.",
            "merchant_name": "Oak & Iron Tavern",
            "currency": "$",
            "items": [
                {"item_name": "Smoked Ribs", "quantity": 1, "price": 28.00},
                {"item_name": "Mac & Cheese", "quantity": 1, "price": 12.00},
                {"item_name": "Draft Cider", "quantity": 2, "price": 14.00},
            ],
            "subtotal": 54.00,
            "taxes": 4.86,
            "service_charge": 10.00,  # Tip written in
            "discounts": 0.0,
            "grand_total": 68.86,
            "confidence": {"merchant_name": 0.93, "line_items": 0.91, "subtotal": 0.92, "taxes": 0.88, "service_charge": 0.72, "grand_total": 0.79},
            "faded": False,
            "crumpled": False,
            "angled": False,
            "handwritten_note": "Tip: $10.00  Total: $68.86  - Thanks!",
        },
        {
            "id": "10_faded_thermal_ink",
            "name": "Faded Thermal Paper Ink",
            "description": "Low-contrast faded cash register paper testing OCR robustness under poor legibility.",
            "merchant_name": "Corner Grocery & Deli",
            "currency": "$",
            "items": [
                {"item_name": "Turkey Club Wrap", "quantity": 1, "price": 9.75},
                {"item_name": "Cold Brew Coffee", "quantity": 1, "price": 4.50},
                {"item_name": "Kettle Chips", "quantity": 1, "price": 2.25},
            ],
            "subtotal": 16.50,
            "taxes": 1.15,
            "service_charge": 0.0,
            "discounts": 0.0,
            "grand_total": 17.65,
            "confidence": {"merchant_name": 0.72, "line_items": 0.68, "subtotal": 0.71, "taxes": 0.65, "grand_total": 0.74},
            "faded": True,
            "crumpled": False,
            "angled": False,
        },
        {
            "id": "11_single_item_expensive",
            "name": "Asymmetric Item Pricing (Fairness Test)",
            "description": "One party orders an expensive $120 vintage wine, while others have $10 tapas. Proves proportional tax fairness.",
            "merchant_name": "Grand Reserve Steakhouse",
            "currency": "$",
            "items": [
                {"item_name": "Dom Perignon 2012", "quantity": 1, "price": 120.00},
                {"item_name": "Truffle Fries", "quantity": 1, "price": 12.00},
                {"item_name": "Sliders Trio", "quantity": 1, "price": 14.00},
            ],
            "subtotal": 146.00,
            "taxes": 14.60,  # 10%
            "service_charge": 14.60,  # 10%
            "discounts": 0.0,
            "grand_total": 175.20,
            "confidence": {"merchant_name": 0.96, "line_items": 0.94, "subtotal": 0.95, "taxes": 0.95, "grand_total": 0.97},
            "faded": False,
            "crumpled": False,
            "angled": False,
        },
        {
            "id": "12_zero_food_subtotal",
            "name": "Zero Food Subtotal (Cover Fee Only)",
            "description": "Venue reservation or entry cover fee with $0 raw food consumed. Tests fallback equal fee distribution.",
            "merchant_name": "Velvet Room Lounge",
            "currency": "$",
            "items": [
                {"item_name": "VIP Table Reservation", "quantity": 1, "price": 0.00},
            ],
            "subtotal": 0.00,
            "taxes": 5.00,
            "service_charge": 50.00,
            "discounts": 0.0,
            "grand_total": 55.00,
            "confidence": {"merchant_name": 0.91, "line_items": 0.88, "subtotal": 0.90, "taxes": 0.89, "grand_total": 0.92},
            "faded": False,
            "crumpled": False,
            "angled": False,
        },
    ]

    manifest = {}

    for ec in edge_cases:
        img_filename = f"{ec['id']}.png"
        create_receipt_image(
            filename=img_filename,
            merchant=ec["merchant_name"],
            items=ec["items"],
            subtotal=ec["subtotal"],
            taxes=ec["taxes"],
            service_charge=ec["service_charge"],
            discounts=ec["discounts"],
            grand_total=ec["grand_total"],
            currency=ec.get("currency", "$"),
            extra_text=ec.get("extra_text"),
            faded=ec.get("faded", False),
            crumpled=ec.get("crumpled", False),
            angled=ec.get("angled", False),
            handwritten_note=ec.get("handwritten_note"),
        )
        manifest[ec["id"]] = {
            "id": ec["id"],
            "name": ec["name"],
            "description": ec["description"],
            "image_filename": img_filename,
            "ground_truth": {
                "merchant_name": ec["merchant_name"],
                "line_items": ec["items"],
                "subtotal": ec["subtotal"],
                "taxes": ec["taxes"],
                "service_charge": ec["service_charge"],
                "discounts": ec["discounts"],
                "grand_total": ec["grand_total"],
                "currency": ec.get("currency", "$"),
                "field_confidence": ec.get("confidence", {}),
            }
        }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated 12 edge case receipts and saved manifest to {MANIFEST_PATH}")


if __name__ == "__main__":
    generate_all_12_edge_cases()
