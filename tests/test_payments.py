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