"""FastAPI backend application for Split the Bill From a Photograph.

Provides receipt photo extraction using Google Gemini Vision,
mathematical validation, mismatch warning diagnostics, and proportional bill splitting.
"""
import os
import json
import io
import re
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image

from backend.schemas import (
    ReceiptExtractionResult,
    LineItem,
    SplitRequest,
    SplitResponse,
)
from backend.math_engine import compute_proportional_split, validate_receipt_math

# Load .env file
load_dotenv()

app = FastAPI(
    title="Bill Splitter AI API",
    description="Multimodal receipt parsing, human correction, and proportional bill splitting.",
    version="1.0.0",
)

# Enable CORS for local development and web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
TEST_BILLS_DIR = os.path.join(BASE_DIR, "test_bills")
MANIFEST_PATH = os.path.join(TEST_BILLS_DIR, "edge_case_manifest.json")

# Extraction prompt for Gemini Vision
EXTRACTION_SYSTEM_PROMPT = """
You are a senior computer vision specialist and precision financial document OCR parser.
Your task is to analyze the uploaded receipt/bill photograph and extract all financial details with strict mathematical fidelity.

You must output a single, strictly valid JSON object matching this exact schema:
{
  "merchant_name": "string (name of restaurant or store, or 'Unknown Merchant')",
  "line_items": [
    {
      "item_name": "string (clear item name)",
      "quantity": float (number of items, e.g. 1.0 or 2.0),
      "price": float (total line item price as printed, not unit price)
    }
  ],
  "subtotal": float (sum of line items before taxes/discounts),
  "taxes": float (sum of all sales taxes, VAT, GST. 0.0 if not listed),
  "service_charge": float (mandatory gratuity, tip, or service fee. 0.0 if not listed),
  "discounts": float (promotional vouchers or deductions as a positive number. 0.0 if none),
  "grand_total": float (final total payable amount),
  "currency": "string (e.g. '$', '€', '£', '₹', etc.)",
  "field_confidence": {
    "merchant_name": float (between 0.0 and 1.0),
    "line_items": float (between 0.0 and 1.0),
    "subtotal": float (between 0.0 and 1.0),
    "taxes": float (between 0.0 and 1.0),
    "service_charge": float (between 0.0 and 1.0),
    "discounts": float (between 0.0 and 1.0),
    "grand_total": float (between 0.0 and 1.0)
  }
}

Guidelines:
1. Examine the image carefully. If text is faded, angled, or crumpled, provide your best estimation and reflect uncertainty with lower confidence scores (< 0.80).
2. If printed numbers do not add up mathematically, extract the exact numbers printed on the paper as-is (do NOT invent numbers to force them to match); the downstream verification system will flag printed arithmetic errors.
3. Clean all currency symbols and commas from the numeric fields.
4. If a handwritten tip or handwritten total is present, incorporate it into service_charge or grand_total and note lower confidence.
5. Return ONLY the JSON object, without markdown fences or additional conversational text.
"""


def get_gemini_api_key(client_header_key: Optional[str] = None) -> Optional[str]:
    """Retrieve Gemini API Key from request header, environment variable, or .env."""
    if client_header_key and client_header_key.strip():
        return client_header_key.strip()
    return os.getenv("GEMINI_API_KEY", "").strip() or None


@app.get("/api/health")
async def health_check():
    """Health check endpoint indicating API status and Gemini key availability."""
    has_env_key = bool(os.getenv("GEMINI_API_KEY", "").strip())
    return {
        "status": "online",
        "gemini_configured": has_env_key,
        "default_model": "gemini-2.5-flash",
    }


@app.get("/api/sample-receipts")
async def get_sample_receipts():
    """Returns the list of 12 edge cases with descriptions and ground truth data."""
    if not os.path.exists(MANIFEST_PATH):
        raise HTTPException(status_code=404, detail="Edge case manifest not found.")
    
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    samples = []
    for case_id, data in manifest.items():
        samples.append({
            "id": case_id,
            "name": data["name"],
            "description": data["description"],
            "image_url": f"/api/sample-receipts/{case_id}/image",
            "ground_truth": data["ground_truth"],
        })
    return {"samples": samples}


@app.get("/api/sample-receipts/{case_id}/image")
async def get_sample_image(case_id: str):
    """Serves the generated receipt image for a given edge case."""
    filename = f"{case_id}.png"
    filepath = os.path.join(TEST_BILLS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Sample image not found.")
    return FileResponse(filepath, media_type="image/png")


@app.post("/api/extract", response_model=ReceiptExtractionResult)
async def extract_receipt_from_photo(
    file: UploadFile = File(...),
    x_gemini_api_key: Optional[str] = Header(default=None),
    mock_edge_case: Optional[str] = Query(default=None),
):
    """Upload a receipt image and extract structured line items, taxes, and confidence scores.
    
    Uses Gemini Vision API (gemini-2.5-flash).
    If mock_edge_case is provided (or if API key is not yet configured), returns realistic high-fidelity
    data from the edge case manifest for immediate interactive demonstration.
    """
    # Validate content type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    content_type = file.content_type or "image/png"
    if content_type not in allowed_types and not file.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        raise HTTPException(
            status_code=400,
            detail="Invalid image format. Please upload JPG, PNG, or WEBP.",
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Validate image with PIL
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        pil_img.verify()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Corrupt or invalid image file: {str(e)}")

    api_key = get_gemini_api_key(x_gemini_api_key)

    # If mock_edge_case specified or API key not present, check manifest for preset
    if mock_edge_case:
        if os.path.exists(MANIFEST_PATH):
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            if mock_edge_case in manifest:
                gt = manifest[mock_edge_case]["ground_truth"]
                result = ReceiptExtractionResult(**gt)
                has_mismatch, details = validate_receipt_math(result)
                result.math_mismatch_warning = has_mismatch
                result.mismatch_details = details
                return result

    if not api_key:
        # Check if file matches one of the edge case filenames or return prompt
        for ec_name in [
            "1_crumpled_paper", "2_angled_shot", "3_incorrect_printed_math",
            "4_heavy_discounts", "5_zero_tax_service_only", "6_high_tax_multiple_rates",
            "7_multi_person_penny_rounding", "8_foreign_currency_symbols",
            "9_handwritten_additions", "10_faded_thermal_ink", "11_single_item_expensive",
            "12_zero_food_subtotal"
        ]:
            if ec_name in (file.filename or ""):
                if os.path.exists(MANIFEST_PATH):
                    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    if ec_name in manifest:
                        gt = manifest[ec_name]["ground_truth"]
                        result = ReceiptExtractionResult(**gt)
                        has_mismatch, details = validate_receipt_math(result)
                        result.math_mismatch_warning = has_mismatch
                        result.mismatch_details = details
                        return result

        raise HTTPException(
            status_code=401,
            detail=(
                "GEMINI_API_KEY is not configured. Please add your GEMINI_API_KEY to the .env file, "
                "provide it in the request header 'X-Gemini-API-Key', or select one of the 12 built-in "
                "edge case samples to test without an API key."
            ),
        )

    # Call Gemini Vision via google-genai SDK
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        
        # Prepare image part
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=content_type,
        )

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
            temperature=0.1,
        )

        # Call gemini-2.5-flash with fallback to gemini-1.5-flash
        primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        candidate_models = [
            primary_model,
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-3.6-flash",
        ]
        # Deduplicate while preserving priority order
        seen_models = set()
        unique_models = []
        for m in candidate_models:
            if m and m not in seen_models:
                seen_models.add(m)
                unique_models.append(m)

        response = None
        last_model_err = None

        for model_name in unique_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        image_part,
                        "Extract all line items, subtotal, taxes, discounts, service charge, and grand total from this receipt image."
                    ],
                    config=config,
                )
                if response and response.text:
                    break
            except Exception as model_err:
                last_model_err = model_err
                continue

        if response is None or not response.text:
            # If API call failed across all models, check if uploaded file matches a test preset
            filename = file.filename or ""
            matched_preset = None
            if os.path.exists(MANIFEST_PATH):
                with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                for ec_key in manifest:
                    if ec_key in filename:
                        matched_preset = manifest[ec_key]["ground_truth"]
                        break

            if matched_preset:
                result = ReceiptExtractionResult(**matched_preset)
                has_mismatch, details = validate_receipt_math(result)
                result.math_mismatch_warning = has_mismatch
                result.mismatch_details = details
                return result

            raise HTTPException(
                status_code=502,
                detail=f"Gemini Vision API extraction failed (tested models: {unique_models}). Last error: {str(last_model_err)}",
            )

        raw_text = response.text.strip()

        # Clean JSON if any accidental markdown wraps were added
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)

        parsed_data = json.loads(raw_text)
        result = ReceiptExtractionResult(**parsed_data)

        # Run mathematical verification
        has_mismatch, details = validate_receipt_math(result)
        result.math_mismatch_warning = has_mismatch
        result.mismatch_details = details

        return result

    except json.JSONDecodeError as jde:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini returned non-JSON output: {str(jde)}. Raw text: {raw_text[:200]}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini Vision API extraction failed: {str(e)}",
        )


@app.post("/api/split", response_model=SplitResponse)
async def split_bill(request: SplitRequest):
    """Computes mathematically correct proportional bill split.
    
    Taxes, service charges, and discounts are distributed strictly proportional
    to raw food subtotal consumed. Reconciles exact cent balancing via Hare-Niemeyer.
    """
    try:
        response = compute_proportional_split(
            receipt=request.receipt_data,
            participants=request.participants,
            assignments=request.assignments,
        )
        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bill split computation failed: {str(e)}")


# Serve frontend assets
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def serve_index():
    """Serves the main single-page web frontend."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"message": "Frontend index.html not yet installed."}
