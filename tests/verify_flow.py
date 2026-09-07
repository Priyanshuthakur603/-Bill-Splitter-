"""End-to-end HTTP verification script testing the live server."""
import httpx
import json

BASE_URL = "http://127.0.0.1:8001"

def test_live_server_full_flow():
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Health check
        health = client.get("/api/health")
        assert health.status_code == 200
        print("[OK] 1. Health check OK:", health.json())

        # 2. Frontend HTML
        index = client.get("/")
        assert index.status_code == 200
        html = index.text
        assert "SmartSplit AI" in html
        assert "dropzone" in html
        assert "mismatch-banner" in html
        assert "split-summary-tbody" in html
        print("[OK] 2. Frontend HTML & DOM elements verified (length:", len(html), "bytes)")

        # 3. Static styles
        styles = client.get("/static/styles.css")
        assert styles.status_code == 200
        assert "glass-panel" in styles.text
        print("[OK] 3. Static stylesheet verified (length:", len(styles.text), "bytes)")

        # 4. Sample Receipts Manifest (12 Edge Cases)
        samples_res = client.get("/api/sample-receipts")
        assert samples_res.status_code == 200
        samples = samples_res.json()["samples"]
        assert len(samples) == 12
        print(f"[OK] 4. All 12 Edge Cases loaded successfully from API:")
        for idx, s in enumerate(samples, 1):
            print(f"   {idx:2d}. {s['id']}: {s['name']} (Total: {s['ground_truth']['currency']}{s['ground_truth']['grand_total']})")

        # 5. Verify sample image serving
        img_res = client.get(samples[0]["image_url"])
        assert img_res.status_code == 200
        assert img_res.headers["content-type"] == "image/png"
        print(f"[OK] 5. Sample receipt image endpoint serving binary PNG ({len(img_res.content)} bytes)")

        # 6. Simulate Full User Workflow with Edge Case 3 (Incorrect Printed Math)
        case3 = next(s for s in samples if s["id"] == "3_incorrect_printed_math")
        gt = case3["ground_truth"]

        # Calculate split before reconciliation (discrepancy exists)
        payload_unreconciled = {
            "receipt_data": gt,
            "participants": [
                {"id": "p1", "name": "Rahul"},
                {"id": "p2", "name": "Priya"},
                {"id": "p3", "name": "Amit"},
                {"id": "p4", "name": "Kavita"},
            ],
            "assignments": [
                {"item_index": 0, "assigned_participant_ids": ["p1"]},          # Classic Burger (15.00)
                {"item_index": 1, "assigned_participant_ids": ["p2", "p4"]},    # Curly Fries (6.00 / 2 = 3.00 each)
                {"item_index": 2, "assigned_participant_ids": ["p3"]},          # Vanilla Shake (7.00)
                {"item_index": 3, "assigned_participant_ids": ["p4"]},          # Hot Dog (10.00)
            ],
        }

        split_unrec = client.post("/api/split", json=payload_unreconciled)
        assert split_unrec.status_code == 200
        res_unrec = split_unrec.json()
        print("\n[OK] 6. Simulated Split with Kavita & Edge Case 3:")
        print(f"   Calculated Total: ${res_unrec['calculated_grand_total']:.2f} === Grand Target: ${res_unrec['receipt_grand_total']:.2f}")
        print(f"   Is Balanced down to the cent: {res_unrec['is_balanced']}")
        for share in res_unrec["shares"]:
            print(f"   - {share['name']:8s}: Food=${share['food_subtotal']:5.2f}, Fee=${share['proportional_fee_share']:5.2f} -> Total=${share['final_total']:5.2f}")

        # 7. Simulate User Clicking 'Sync Subtotal with Items Sum' (Auto-Reconcile)
        # Items sum is 15 + 6 + 7 + 10 = 38.00. Tax is 3.78. Grand total = 41.78.
        reconciled_gt = dict(gt)
        reconciled_gt["subtotal"] = 38.00
        reconciled_gt["grand_total"] = 41.78

        payload_reconciled = dict(payload_unreconciled)
        payload_reconciled["receipt_data"] = reconciled_gt

        split_rec = client.post("/api/split", json=payload_reconciled)
        assert split_rec.status_code == 200
        res_rec = split_rec.json()
        print("\n[OK] 7. Simulated 'Sync Subtotal' Reconciled Split:")
        print(f"   Calculated Total: ${res_rec['calculated_grand_total']:.2f} === Grand Target: ${res_rec['receipt_grand_total']:.2f}")
        print(f"   Is Balanced: {res_rec['is_balanced']}")
        for share in res_rec["shares"]:
            print(f"   - {share['name']:8s}: Food=${share['food_subtotal']:5.2f}, Fee=${share['proportional_fee_share']:5.2f} -> Total=${share['final_total']:5.2f}")

        # Verify penny sum
        penny_sum = round(sum(s["final_total"] for s in res_rec["shares"]), 2)
        assert penny_sum == 41.78
        print(f"\n[OK] 8. Penny-perfect invariant verified: sum({penny_sum}) == 41.78 exact balance!")

if __name__ == "__main__":
    test_live_server_full_flow()
