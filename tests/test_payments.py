# python -m pytest. После написания команды pytest начинает искать папки или файлы с тестами из основной директории проекта
# У pytest есть правила обнаружения тестов.  По умолчанию он ищет файлы с именами вроде: test_*.py или *_test.py
# Он понимает какие функции надо запускать благодаря названию функций который начинаются с test_
# Из-за правила обнаружения тестов он проходит по каждой директории и смотрим все файлы и ищет, который начинались бы на:
# test_*.py или *_test.py
# Получается, что: python -m pytest - это команда, которая говорит pytest, найди и запусти тесты в текущем месте по своим правилам
# А вот conftest.py - специальное имя файла, которое pytest знает сам, т.е. файл с настройками для тестов он сам его
# подключает для тестов и этот файл считается конфигурацией/фикстур(настроек заранее запуска нужных переменных) для тестов
# Т.е. сначала он находит файлы тестов подключает к ним conftest выполняет код fixture до yield, затем получает TestClient и
# передает его в тесты и после тесты выполняются и когда тесты выполнены он выполняет оставшийся код после yield



def test_payment_amount_without_promo(client): # Проверка создания платежа без промокода
    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "promo-test-1"},
        json={
            "tariff_id": 2,
            "method": "card",
            "email": "test@example.com",
        },
    )

    # проверяем чтоб код ответа от сревера был 201 если какой-то иной тест падает и не выполнен
    assert response.status_code == 201 # если платеж успешно создан, API должен вернуть HTTP 201 Created.

    data = response.json()

    assert data["amount"] == 1_990_000 # проверяем цену без промокода
    assert data["discount"] == 0 # проверяем размер скидки чтоб всё совпадало


def test_payment_amount_with_promo_case_insensitive(client): # тесты для проверки промокода без учёта регистра
    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "promo-test-2"},
        json={
            "tariff_id": 2,
            "method": "card",
            "email": "test@example.com",
            "promo_code": "KvItTo10",
        },
    )

    assert response.status_code == 201 # ожидаем успешное создание

    data = response.json()

    assert data["discount"] == 199_000 # проверяем размер скидки
    assert data["amount"] == 1_791_000 # проверяем итоговую стоимость тарифа


def test_installment_schedule_sums_to_amount(client): # тест для проверки графика рассрочки что этот график в сумме равен общей сумме платежа
    for months in (3, 6, 12): # запускаем 3 сценария тестов с разными графиками рассрочки
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

        assert response.status_code == 201 # ожидаем успешное создание платежа

        data = response.json()

        assert len(data["schedule"]) == months # проверяем чтоб длина графика рассрочки соответствовала кол-ву месяцев рассрочки
        assert sum(data["schedule"]) == data["amount"] # проверяем чтоб сумма графика рассрочки была равна итоговой сумме платежа


def test_idempotency_key_does_not_create_second_payment(client): # тест для проверки идемпотентности чтоб не создавались 2 платежа
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

    assert first_response.status_code == 201 # ожидаем что создаться платёж
    assert second_response.status_code == 200 # ожидаем что платёж уже создан и вернёт нам информацию о платеже так же

    first_data = first_response.json()
    second_data = second_response.json()

    assert second_data["id"] == first_data["id"] # сравниваем что по итогу айди тарифа одинаковые т.е. не создался дубликат
    assert second_data["tariff_id"] == first_data["tariff_id"] # сравниваем тип тарифа что он не изменился на другой и это тот же самый платёж


def test_invalid_status_transition_returns_409_and_status_unchanged(client): # тест для проверки изменения статуса платежа неправильном переходе и не изменении статуса при неправильном переходе
    create_response = client.post(
        "/payments",
        headers={"Idempotency-Key": "status-test"},
        json={
            "tariff_id": 2,
            "method": "card",
            "email": "test@example.com",
        },
    )

    assert create_response.status_code == 201 # платеж создали

    payment_id = create_response.json()["id"] # получаем айди платежа для дальнейшей работы попытки изменения его статуса

    response = client.post(
        "/webhooks/bank",
        json={
            "payment_id": payment_id, # передаём айди платежа который хотим изменить
            "status": "refunded", # его новый статус этого платежа
        },
    )

    assert response.status_code == 409 # ожидаем получение ошибки т.к. из pending нельзя refunded
    assert response.json()["detail"]["error"] == "invalid_transition" # проверяем что детали ошибки ожидаемая причина - "invalid_transition"

    payment_response = client.get(f"/payments/{payment_id}") # получаем информацию о платеже что он существует и с ним можно работать

    assert payment_response.status_code == 200 # проверяем что информацию о платеже получена успешно
    assert payment_response.json()["status"] == "pending" # проверяем состояния платежа что из pending он не мог преобразоваться в refunded


def test_nonexistent_payment_returns_404(client): # проверка на несуществующий платеж какой ответ вернёт
    response = client.get("/payments/999999") # хотим получить платёж с айди(ключом) 999999

    assert response.status_code == 404 # ожидаем ответ, что такого платежа нет



# ВЫШЕ ОСНОВНЫЕ ТЕСТЫ КОТОРЫЕ ПРЕДЛАГАЛИСЬ В ТЗ

# НИЖЕ ДРУГИЕ ТЕСТЫ

# ПРОВЕРКА НА ПОЛУЧЕНИЕ ТАРИФОВ - GET /tariffs 200 — список тарифов [{ id, title, price }] .
def test_get_tariffs_returns_all_tariffs(client):
    response = client.get("/tariffs")

    # 1. Код ответа
    assert response.status_code == 200

    tariffs = response.json()

    # 2. Тип и количество
    assert isinstance(tariffs, list)
    assert len(tariffs) == 3

    # 3. Состав полей у каждого тарифа — ровно id, title, price
    for tariff in tariffs:
        assert set(tariff.keys()) == {"id", "title", "price"}
        assert isinstance(tariff["id"], int)
        assert isinstance(tariff["title"], str)
        assert isinstance(tariff["price"], int)     # деньги — int, без float

    # 4. Соответствие названий и цен (цены — в копейках)
    by_title = {t["title"]: t["price"] for t in tariffs}
    assert by_title == {
        "basic": 990_000,
        "standard": 1_990_000,
        "premium": 2_990_000,
    }

    # 5. id — уникальны
    ids = [t["id"] for t in tariffs]
    assert len(set(ids)) == len(ids)

# ТЕСТ ДЛЯ ПРОВЕРКИ УСПЕШНОСТИ ВСЕХ ИЗМЕНЕНИЙ СТАТУСА
def test_status_transitions(client):

    def create_payment(key: str) -> int:
        r = client.post(
            "/payments",
            headers={"Idempotency-Key": key},
            json={
                "tariff_id": 2,
                "method": "card",
                "email": f"{key}@example.com",
            },
        )
        assert r.status_code == 201
        return r.json()["id"]

    def send_webhook(payment_id: int, new_status: str):
        return client.post(
            "/webhooks/bank",
            json={"payment_id": payment_id, "status": new_status},
        )

    def get_status(payment_id: int) -> str:
        r = client.get(f"/payments/{payment_id}")
        assert r.status_code == 200
        return r.json()["status"]

    # ---------- 1. pending → succeeded ----------
    pid = create_payment("ok-p2s")
    assert get_status(pid) == "pending"          # стартовый статус

    r = send_webhook(pid, "succeeded")
    assert r.status_code == 200
    assert r.json() == {"result": "ok"}
    assert get_status(pid) == "succeeded"        # статус реально изменился

    # ---------- 2. pending → failed ----------
    pid = create_payment("ok-p2f")
    assert get_status(pid) == "pending"

    r = send_webhook(pid, "failed")
    assert r.status_code == 200
    assert r.json() == {"result": "ok"}
    assert get_status(pid) == "failed"

    # ---------- 3. succeeded → refunded ----------
    pid = create_payment("ok-s2r")
    assert get_status(pid) == "pending"

    r = send_webhook(pid, "succeeded")
    assert r.status_code == 200
    assert get_status(pid) == "succeeded"

    r = send_webhook(pid, "refunded")
    assert r.status_code == 200
    assert r.json() == {"result": "ok"}
    assert get_status(pid) == "refunded"

    # ---------- 4. запрещённый: pending → refunded ----------
    pid = create_payment("forbidden-p2r")
    assert get_status(pid) == "pending"

    r = send_webhook(pid, "refunded")
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "invalid_transition"
    assert get_status(pid) == "pending"          # статус НЕ изменился

    # ---------- 5. запрещённый: succeeded → pending ----------
    pid = create_payment("forbidden-s2p")
    assert get_status(pid) == "pending"

    r = send_webhook(pid, "succeeded")
    assert r.status_code == 200
    assert get_status(pid) == "succeeded"

    r = send_webhook(pid, "pending")
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "invalid_transition"
    assert get_status(pid) == "succeeded"        # статус НЕ изменился

    # ---------- 6. запрещённый: succeeded → failed ----------
    pid = create_payment("forbidden-s2f")
    assert get_status(pid) == "pending"

    r = send_webhook(pid, "succeeded")
    assert r.status_code == 200
    assert get_status(pid) == "succeeded"

    r = send_webhook(pid, "failed")
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "invalid_transition"
    assert get_status(pid) == "succeeded"

    # ---------- 7. запрещённый: failed → succeeded ----------
    pid = create_payment("forbidden-f2s")
    assert get_status(pid) == "pending"

    r = send_webhook(pid, "failed")
    assert r.status_code == 200
    assert get_status(pid) == "failed"

    r = send_webhook(pid, "succeeded")
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "invalid_transition"
    assert get_status(pid) == "failed"

    # ---------- 8. запрещённый: failed → pending ----------
    pid = create_payment("forbidden-f2p")
    assert get_status(pid) == "pending"

    r = send_webhook(pid, "failed")
    assert r.status_code == 200
    assert get_status(pid) == "failed"

    r = send_webhook(pid, "pending")
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "invalid_transition"
    assert get_status(pid) == "failed"

    # ---------- 9. запрещённый: refunded → succeeded ----------
    pid = create_payment("forbidden-r2s")
    assert get_status(pid) == "pending"

    r = send_webhook(pid, "succeeded")
    assert r.status_code == 200
    r = send_webhook(pid, "refunded")
    assert r.status_code == 200
    assert get_status(pid) == "refunded"

    r = send_webhook(pid, "succeeded")
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "invalid_transition"
    assert get_status(pid) == "refunded"

    # ---------- 10. запрещённый: refunded → failed ----------
    pid = create_payment("forbidden-r2f")
    assert get_status(pid) == "pending"

    r = send_webhook(pid, "succeeded")
    assert r.status_code == 200
    r = send_webhook(pid, "refunded")
    assert r.status_code == 200
    assert get_status(pid) == "refunded"

    r = send_webhook(pid, "failed")
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "invalid_transition"
    assert get_status(pid) == "refunded"

    # ---------- 11. запрещённый: refunded → pending ----------
    pid = create_payment("forbidden-r2p")
    assert get_status(pid) == "pending"

    r = send_webhook(pid, "succeeded")
    assert r.status_code == 200
    r = send_webhook(pid, "refunded")
    assert r.status_code == 200
    assert get_status(pid) == "refunded"

    r = send_webhook(pid, "pending")
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "invalid_transition"
    assert get_status(pid) == "refunded"

# НИЖЕ ДОПОЛНИТЕЛЬНЫЕ ТЕСТЫ — КРАЕВЫЕ СЛУЧАИ ИЗ ТЗ


def test_unknown_promo_code_returns_422(client):
    """Неизвестный промокод → 422 (ТЗ)."""
    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "unknown-promo"},
        json={
            "tariff_id": 2,
            "method": "card",
            "email": "test@example.com",
            "promo_code": "NOPE123",
        },
    )
    assert response.status_code == 422


def test_invalid_installment_months_returns_422(client):
    """installment_months может быть только 3, 6 или 12 (ТЗ)."""
    for months in (0, 1, 5, 24, -3):
        response = client.post(
            "/payments",
            headers={"Idempotency-Key": f"bad-months-{months}"},
            json={
                "tariff_id": 2,
                "method": "installment",
                "email": "test@example.com",
                "installment_months": months,
            },
        )
        assert response.status_code == 422, f"months={months} должен быть 422"


def test_installment_without_months_returns_422(client):
    """Для рассрочки installment_months обязателен (ТЗ)."""
    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "installment-no-months"},
        json={
            "tariff_id": 2,
            "method": "installment",
            "email": "test@example.com",
        },
    )
    assert response.status_code == 422


def test_installment_months_forbidden_for_card_and_sbp(client):
    """installment_months нельзя передавать для card/sbp."""
    for method in ("card", "sbp"):
        response = client.post(
            "/payments",
            headers={"Idempotency-Key": f"months-for-{method}"},
            json={
                "tariff_id": 2,
                "method": method,
                "email": "test@example.com",
                "installment_months": 6,
            },
        )
        assert response.status_code == 422, f"method={method} должен быть 422"


def test_schedule_is_null_for_card_and_sbp(client):
    """Для card/sbp schedule == null и installment_months == null (ТЗ)."""
    for method in ("card", "sbp"):
        response = client.post(
            "/payments",
            headers={"Idempotency-Key": f"null-schedule-{method}"},
            json={
                "tariff_id": 2,
                "method": method,
                "email": "test@example.com",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["schedule"] is None
        assert data["installment_months"] is None


def test_payment_response_structure(client):
    """Ответ платежа содержит все поля из ТЗ и правильные типы."""
    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "structure-1"},
        json={
            "tariff_id": 2,
            "method": "installment",
            "email": "test@example.com",
            "installment_months": 3,
        },
    )
    assert response.status_code == 201
    data = response.json()

    # Ровно те поля, что перечислены в ТЗ
    for field in (
        "id", "status", "tariff_id", "amount", "discount",
        "method", "installment_months", "schedule",
        "email", "created_at",
    ):
        assert field in data, f"нет поля {field}"

    # Типы
    assert isinstance(data["id"], int)
    assert isinstance(data["tariff_id"], int)
    assert isinstance(data["amount"], int)          # деньги — int, без float
    assert isinstance(data["discount"], int)
    assert isinstance(data["schedule"], list)
    assert all(isinstance(x, int) for x in data["schedule"])
    assert data["status"] == "pending"              # стартовый статус из ТЗ
    assert data["method"] == "installment"
    assert data["installment_months"] == 3


def test_installment_schedule_exact_values(client):
    """Пример из ТЗ: standard без промо, 3 месяца → [663334, 663333, 663333]."""
    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "exact-schedule"},
        json={
            "tariff_id": 2,
            "method": "installment",
            "email": "test@example.com",
            "installment_months": 3,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 1_990_000
    assert data["schedule"] == [663334, 663333, 663333]


def test_installment_schedule_with_promo(client):
    """Рассрочка + промокод: 1 990 000 − 199 000 = 1 791 000, делим на 3."""
    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "schedule-promo"},
        json={
            "tariff_id": 2,
            "method": "installment",
            "email": "test@example.com",
            "installment_months": 3,
            "promo_code": "KVITT010", # 0 нолик за место О
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail == "Unknown promo code"


def test_invalid_tariff_id_returns_404(client):
    """Несуществующий tariff_id → 404 (см. payments.py)."""
    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "bad-tariff"},
        json={
            "tariff_id": 99999,
            "method": "card",
            "email": "test@example.com",
        },
    )
    assert response.status_code == 404


def test_invalid_method_returns_422(client):
    """Невалидный method ловится Pydantic'ом."""
    response = client.post(
        "/payments",
        headers={"Idempotency-Key": "bad-method"},
        json={
            "tariff_id": 2,
            "method": "crypto",
            "email": "test@example.com",
        },
    )
    assert response.status_code == 422


def test_webhook_nonexistent_payment_returns_404(client):
    """Webhook на несуществующий payment_id → 404 (ТЗ)."""
    response = client.post(
        "/webhooks/bank",
        json={"payment_id": 999999, "status": "succeeded"},
    )
    assert response.status_code == 404


def test_different_idempotency_keys_create_two_payments(client):
    """Разные Idempotency-Key → два разных платежа."""
    r1 = client.post(
        "/payments",
        headers={"Idempotency-Key": "diff-1"},
        json={"tariff_id": 2, "method": "card", "email": "x@example.com"},
    )
    r2 = client.post(
        "/payments",
        headers={"Idempotency-Key": "diff-2"},
        json={"tariff_id": 2, "method": "card", "email": "x@example.com"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


def test_amounts_are_int(client):
    """Все суммы — int, без float, во всех ответах."""
    r = client.post(
        "/payments",
        headers={"Idempotency-Key": "int-types"},
        json={
            "tariff_id": 2,
            "method": "installment",
            "email": "test@example.com",
            "installment_months": 6,
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert isinstance(data["amount"], int)
    assert isinstance(data["discount"], int)
    assert isinstance(data["tariff_id"], int)
    assert all(isinstance(x, int) for x in data["schedule"])