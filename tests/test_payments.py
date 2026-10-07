def test_payment_amount_without_promo(client):
    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "promo-test-1"},
        json={
            "tariff_id": 2,
            "method": "card",
            "email": "test@example.com",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["amount"] == 1_990_000
    assert data["discount"] == 0


def test_payment_amount_with_promo_case_insensitive(client):
    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "promo-test-2"},
        json={
            "tariff_id": 2,
            "method": "card",
            "email": "test@example.com",
            "promo_code": "kvitto10",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["discount"] == 199_000
    assert data["amount"] == 1_791_000


def test_installment_schedule_sums_to_amount(client):
    for months in (3, 6, 12):
        response = client.post(
            "/payments",
            headers={"Idempotency-Key": f"installment-{months}"},
            json={
                "tariff_id": 2,
                "method": "installment",
                "email": "test@example.com",
                "installment_months": months,
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert len(data["schedule"]) == months
        assert sum(data["schedule"]) == data["amount"]


def test_idempotency_key_does_not_create_second_payment(client):
    first_response = client.post(
        "/payments",
        headers={"Idempotency-Key": "same-key"},
        json={
            "tariff_id": 2,
            "method": "card",
            "email": "test@example.com",
        },
    )

    second_response = client.post(
        "/payments",
        headers={"Idempotency-Key": "same-key"},
        json={
            "tariff_id": 3,
            "method": "card",
            "email": "another@example.com",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200

    first_data = first_response.json()
    second_data = second_response.json()

    assert second_data["id"] == first_data["id"]
    assert second_data["tariff_id"] == first_data["tariff_id"]


def test_invalid_status_transition_returns_409_and_status_unchanged(client):
    create_response = client.post(
        "/payments",
        headers={"Idempotency-Key": "status-test"},
        json={
            "tariff_id": 2,
            "method": "card",
            "email": "test@example.com",
        },
    )

    assert create_response.status_code == 201

    payment_id = create_response.json()["id"]

    response = client.post(
        "/webhooks/bank",
        json={
            "payment_id": payment_id,
            "status": "refunded",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "invalid_transition"

    payment_response = client.get(f"/payments/{payment_id}")

    assert payment_response.status_code == 200
    assert payment_response.json()["status"] == "pending"


def test_nonexistent_payment_returns_404(client):
    response = client.get("/payments/999999")

    assert response.status_code == 404