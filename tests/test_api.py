"""Integration tests for FastAPI endpoints."""
import os
import pytest
from fastapi.testclient import TestClient
from backend.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "gemini_configured" in data


def test_index_page_serving(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "SmartSplit AI" in response.text


def test_get_sample_receipts(client):
    response = client.get("/api/sample-receipts")
    assert response.status_code == 200
    data = response.json()
    assert "samples" in data
    assert len(data["samples"]) == 12

    # Check first sample has all required fields
    sample_1 = data["samples"][0]
    assert "id" in sample_1
    assert "name" in sample_1
    assert "description" in sample_1
    assert "image_url" in sample_1
    assert "ground_truth" in sample_1


def test_sample_receipt_image_serving(client):
    response = client.get("/api/sample-receipts/1_crumpled_paper/image")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 1000


def test_split_endpoint_calculation(client):
    payload = {
        "receipt_data": {
            "merchant_name": "Test Diner",
            "line_items": [
                {"item_name": "Pancake Stack", "quantity": 1, "price": 12.00},
                {"item_name": "Omelette Deluxe", "quantity": 1, "price": 16.00},
                {"item_name": "Fresh Orange Juice", "quantity": 2, "price": 8.00},
            ],
            "subtotal": 36.00,
            "taxes": 3.60,
            "service_charge": 0.0,
            "discounts": 0.0,
            "grand_total": 39.60,
            "field_confidence": {},
            "currency": "$",
            "math_mismatch_warning": False,
        },
        "participants": [
            {"id": "p1", "name": "Rahul"},
            {"id": "p2", "name": "Priya"},
        ],
        "assignments": [
            {"item_index": 0, "assigned_participant_ids": ["p1"]},  # 12.00
            {"item_index": 1, "assigned_participant_ids": ["p2"]},  # 16.00
            {"item_index": 2, "assigned_participant_ids": ["p1", "p2"]},  # 8.00 split 4.00 each
        ],
    }

    response = client.post("/api/split", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Rahul food: 12 + 4 = 16. Priya food: 16 + 4 = 20. Total: 36.
    # Tax: 3.60. Rahul tax: 3.60 * (16/36) = 1.60. Priya tax: 3.60 * (20/36) = 2.00.
    # Rahul final: 17.60. Priya final: 22.00. Total = 39.60.
    rahul = next(s for s in data["shares"] if s["participant_id"] == "p1")
    priya = next(s for s in data["shares"] if s["participant_id"] == "p2")

    assert rahul["food_subtotal"] == 16.00
    assert rahul["final_total"] == 17.60
    assert priya["food_subtotal"] == 20.00
    assert priya["final_total"] == 22.00

    assert data["calculated_grand_total"] == 39.60
    assert data["is_balanced"] is True


def test_extract_mock_edge_case(client):
    """Test the mock preset extraction parameter."""
    sample_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_bills", "1_crumpled_paper.png")
    with open(sample_path, "rb") as f:
        file_bytes = f.read()
    response = client.post("/api/extract?mock_edge_case=1_crumpled_paper", files={"file": ("1_crumpled_paper.png", file_bytes, "image/png")})
    assert response.status_code == 200
    data = response.json()
    assert data["merchant_name"] == "The Bistro Garden"
    assert len(data["line_items"]) == 3
    assert data["grand_total"] == 94.61
    assert "field_confidence" in data
