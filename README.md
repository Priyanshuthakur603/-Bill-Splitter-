# SmartSplit: Split the Bill From a Photograph
> **Production-ready AI web application that parses receipt photos, extracts line items & taxes using Google Gemini Vision, provides human-in-the-loop verification, and calculates mathematically sound proportional bill splits with penny-perfect reconciliation.**

---

## 1. Mathematical Foundation & Fairness Proof

Splitting restaurant and grocery bills equally across participants introduces substantial financial unfairness whenever consumption is asymmetric.

### A. The Flaw of Equal Fee Division
Suppose Person A orders a \$10 snack and Person B orders an \$90 steak (Food Subtotal = \$100). The restaurant assesses a 10% sales tax (\$10.00).
- **Equal Fee Split (Unfair)**: Each person pays \$5.00 tax. Person A pays \$15.00 (a **50% tax rate** on their food). Person B pays \$95.00 (a **5.5% tax rate** on their food).
- **Proportional Fee Split (SmartSplit AI)**: Tax, service charges, and discounts are distributed strictly proportional to raw food subtotal consumed.
  - Person A consumes $\frac{\$10}{\$100} = 10\%$ of food $\rightarrow$ Pays $10\% \times \$10.00 = \$1.00$ tax $\rightarrow$ Final: **\$11.00**.
  - Person B consumes $\frac{\$90}{\$100} = 90\%$ of food $\rightarrow$ Pays $90\% \times \$10.00 = \$9.00$ tax $\rightarrow$ Final: **\$99.00**.

### B. The Proportional Splitting Formula
For participant $i$ consuming a set of items with individual share fractions:
$$\text{Food Subtotal}_i = \sum_{k \in \text{Items}_i} \frac{\text{Price}_k}{\text{Participants Assigned to } k}$$

$$\text{Fee Share}_i = \text{Total Net Fees} \times \left( \frac{\text{Food Subtotal}_i}{\text{Receipt Food Subtotal}} \right)$$

$$\text{Final Total}_i = \text{Food Subtotal}_i + \text{Fee Share}_i$$

where:
$$\text{Total Net Fees} = \text{Taxes} + \text{Service Charge} - \text{Discounts}$$

### C. Penny-Perfect Reconciliation (Hare-Niemeyer Algorithm)
When sharing items among $N$ participants (e.g. 3 people sharing a \$10 dish $\rightarrow \$3.3333\dots$), converting continuous shares to integer cents produces fractional rounding discrepancies.
SmartSplit AI employs the **Largest Remainder Method (Hare-Niemeyer)**:
1. Compute exact continuous shares $E_i = \text{Final Total}_i \times 100$ (in cents).
2. Floor each participant's share: $I_i = \lfloor E_i \rfloor$, tracking remainder fractions $R_i = E_i - I_i$.
3. Compute the penny discrepancy $\Delta = (\text{Receipt Grand Total} \times 100) - \sum I_i$.
4. Award the $\Delta$ remainder cents to the participants having the largest fractional remainders $R_i$.
5. **Guaranteed Invariant**:
   $$\sum_{i=1}^N \text{Final Total}_i \equiv \text{Receipt Grand Total} \quad (\text{exact down to the cent})$$

---

## 2. Architecture & Tech Stack

```
                                  +---------------------------+
                                  |   Receipt Photo Upload    |
                                  |  (JPG, PNG, WEBP, Camera) |
                                  +-------------+-------------+
                                                |
                                                v
                                  +---------------------------+
                                  |   FastAPI Backend (Py)    |
                                  |     /api/extract          |
                                  +-------------+-------------+
                                                |
                       +------------------------+------------------------+
                       |                                                 |
                       v                                                 v
        +-----------------------------+                   +-----------------------------+
        |  Gemini 2.5 Flash Vision    |                   | 12 Edge Case Presets Engine |
        |  - Structured JSON Output   |                   | - Built-in offline testing  |
        |  - Field Confidence Scores  |                   | - Instant 1-click loading   |
        +--------------+--------------+                   +--------------+--------------+
                       |                                                 |
                       +------------------------+------------------------+
                                                |
                                                v
                                  +---------------------------+
                                  |   Human-in-the-Loop UI    |
                                  | - Confidence Badges (<0.8)|
                                  | - Mismatch Alert Banner   |
                                  | - Inline Field Editing    |
                                  | - Dynamic Participant Add |
                                  +-------------+-------------+
                                                |
                                                v
                                  +---------------------------+
                                  |   Proportional Math &     |
                                  |   Cent Reconciliation     |
                                  |      /api/split           |
                                  +-------------+-------------+
                                                |
                                                v
                                  +---------------------------+
                                  |  Balanced Summary Output  |
                                  | - Exact Cent Verified     |
                                  | - WhatsApp/Slack Copy     |
                                  | - JSON Export             |
                                  +---------------------------+
```

### Backend
- **Python 3.14 / 3.11+**
- **FastAPI**: Asynchronous high-performance REST API with CORS support.
- **Pydantic v2**: Strict schema validation, confidence tracking, and data coercion.
- **Google GenAI SDK (`google-genai`)**: Multimodal Vision API (`gemini-2.5-flash`).
- **Pillow (PIL)**: Image decoding, synthetic edge case generation, and texture synthesis.

### Frontend
- **Modern Single-Page Application (HTML5 / Vanilla JS)**: No bloated node build tools required.
- **Tailwind CSS (CDN)**: Sleek, responsive dark-mode slate & indigo glassmorphism.
- **Lucide Icons**: Crisp vector UI iconography.
- **Interactive Canvas**: Drag-and-drop, zoom in/out, rotate 90°, and smooth pan navigation.

---

## 3. Human-in-the-Loop Review System

Computer vision on real-world receipts faces challenges such as crumpling, fading, and tilted camera shots. SmartSplit AI builds confidence through transparency:

1. **Confidence Scores per Field**:
   Each extracted field (`subtotal`, `taxes`, `line_items`, `grand_total`) carries an AI confidence score ($0.0$ to $1.0$).
2. **Soft Yellow Warning Highlights**:
   Any field with confidence $< 0.80$ is visually highlighted with a warning badge and pulse animation, prompting the human reviewer to double check the photo.
3. **Printed Arithmetic Mismatch Banner**:
   If the register's printed line items sum does not match the printed subtotal, a prominent alert banner triggers:
   $$\left| \sum \text{Items} - \text{Subtotal} \right| > 0.05 \implies \text{math\_mismatch\_warning: true}$$
   The user can click **"Sync Subtotal with Items Sum"** for 1-click reconciliation or edit individual line items directly.
4. **Interactive Participant Assignment**:
   - Color-coded chips for each person (e.g. Rahul, Priya, Amit).
   - Assign items to **One Person**, **Multiple People** (equal split of item price), or **Everyone**.
   - Real-time display of per-person cost ($15.00 / 3 = \$5.00/\text{person}$).

---

## 4. The 12 Edge Cases Suite

The `test_bills/` directory contains synthetic receipt images and automated tests verifying 12 real-world edge cases:

| # | Edge Case ID | Name | Description & Verification Goal |
|---|---|---|---|
| 1 | `1_crumpled_paper` | Crumpled Paper Receipt | Degraded, folded receipt paper with wrinkles and shadows affecting OCR clarity. |
| 2 | `2_angled_shot` | Angled Perspective Shot | Camera photo taken at an angle with tilted perspective distortion. |
| 3 | `3_incorrect_printed_math` | Incorrect Printed Math | Cash register error where printed items sum to \$38.00 but printed subtotal is \$42.00. Triggers `math_mismatch_warning: true`. |
| 4 | `4_heavy_discounts` | Heavy Discounts & Vouchers | Bill with substantial promo deduction (-\$35.00) that proportionally reduces participant shares. |
| 5 | `5_zero_tax_service_only` | Zero Tax (Service Only) | Duty-free receipt with 0% sales tax but 12% mandatory service charge. |
| 6 | `6_high_tax_multiple_rates` | Compound Tax Rates | Composite multi-rate taxes (e.g., State 6.25% + Local Meal 2.75% = 9.0% total). |
| 7 | `7_multi_person_penny_rounding` | Multi-Person Penny Rounding | \$10.00 split 3 ways yields \$3.3333. Hare-Niemeyer cent balancing allocates the extra 1 cent without loss. |
| 8 | `8_foreign_currency_symbols` | Foreign Currency (€ / ₹) | International receipt with € (Euro) formatting and European decimal comma support. |
| 9 | `9_handwritten_additions` | Handwritten Tip Addition | Receipt with printed total and customer handwritten tip added in blue pen. |
| 10 | `10_faded_thermal_ink` | Faded Thermal Ink | Low-contrast faded register ink testing low-confidence flags (< 0.80). |
| 11 | `11_single_item_expensive` | Asymmetric Pricing Fairness | One person orders \$120 wine, others have \$12 fries. Confirms proportional tax equity. |
| 12 | `12_zero_food_subtotal` | Zero Food Subtotal | Venue cover fee / table reservation with \$0 food items. Tests fallback equal fee distribution. |

---

## 5. Quickstart & Installation

### Step 1: Install Dependencies
```powershell
pip install fastapi uvicorn pydantic google-genai pillow python-multipart python-dotenv pytest httpx
```

### Step 2: Configure Environment
Create or edit `.env` in the root directory:
```bash
GEMINI_API_KEY=AIzaSy...your_gemini_api_key_here
```
*(Note: If you do not have an API key right now, the application runs seamlessly out-of-the-box using the 12 built-in edge case presets, or you can paste your key in the web UI settings modal!)*

### Step 3: Run the Application Server
```powershell
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

---

## 6. Running Automated Tests

Run the complete test suite covering the proportional math engine, Hare-Niemeyer cent balancing, API endpoints, and all 12 edge cases:

```powershell
python -m pytest test_bills/ tests/ -v
```

All 11 tests will execute and validate:
- Zero-penny loss invariants.
- Proportional fairness checks.
- Discrepancy detection on bad printed receipts.
- Static frontend serving and REST endpoints.

---

## 7. REST API Reference

### `POST /api/extract`
Upload a receipt photo to extract structured line items and taxes.
- **Request**: `multipart/form-data` with `file: UploadFile` (JPG, PNG, WEBP).
- **Headers (Optional)**: `X-Gemini-API-Key: <key>`.
- **Query Params (Optional)**: `mock_edge_case=<id>`.
- **Response**: `ReceiptExtractionResult` JSON with confidence scores and mismatch warnings.

### `POST /api/split`
Calculates proportional shares with cent balancing.
- **Request Body**:
  ```json
  {
    "receipt_data": { ... },
    "participants": [
      { "id": "p1", "name": "Rahul" },
      { "id": "p2", "name": "Priya" }
    ],
    "assignments": [
      { "item_index": 0, "assigned_participant_ids": ["p1", "p2"] }
    ]
  }
  ```
- **Response**: `SplitResponse` JSON showing each participant's consumed items, base food subtotal, proportional fee share, and final total.

### `GET /api/sample-receipts`
Returns metadata and ground truth for all 12 edge cases.

### `GET /api/health`
Status and Gemini API key configuration check.
