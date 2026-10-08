# Kvitto Test Task — Payments API

API для приёма оплаты курсов через Квитто. FastAPI + SQLite + SQLAlchemy.

## Стек

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- SQLite
- pytest + httpx

## Запуск

1. Клонировать репозиторий и перейти в него:

   ```bash
   git clone https://github.com/EndoKardo/kvitto-test-task
   cd kvitto-test-task
   ```

2. Создать и активировать виртуальное окружение:

   ```bash
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # Linux / macOS
   source .venv/bin/activate
   ```

3. Установить зависимости:

   ```bash
   pip install -r requirements.txt
   ```

4. Запустить сервер:

   ```bash
   uvicorn app.main:app --reload
   ```

   При старте приложения автоматически создаются таблицы и три тарифа:
   `basic` — 9 900 ₽, `standard` — 19 900 ₽, `premium` — 29 900 ₽.

5. Открыть Swagger UI: <http://127.0.0.1:8000/docs>

## Тесты

```bash
python -m pytest -v
```

Тесты используют `TestClient` и SQLite в памяти (`sqlite://`), реальная
база `kvitto.db` не затрагивается. Фикстура `client` (в `tests/conftest.py`)
перед каждым тестом создаёт таблицы, добавляет три тарифа и подменяет
зависимость `get_db` на тестовую сессию.

## Примеры запросов

Все примеры ниже — через `curl`. В **PowerShell** `curl` — это псевдоним
для `Invoke-WebRequest`, поэтому нужно писать `curl.exe --%`, иначе команды
с JSON-телом не сработают. В Git Bash / Linux / macOS достаточно `curl`.

### 1. Список тарифов

```bash
curl -s http://127.0.0.1:8000/tariffs
```

Ответ:

```json
[
  {"id": 1, "title": "basic",    "price":  990000},
  {"id": 2, "title": "standard", "price": 1990000},
  {"id": 3, "title": "premium",  "price": 2990000}
]
```

### 2. Создать платёж без промокода

```bash
curl -s -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-key-1" \
  -d '{
    "tariff_id": 2,
    "method": "card",
    "email": "student@example.com"
  }'
```

Ответ (201 Created):

```json
{
  "id": 1,
  "status": "pending",
  "tariff_id": 2,
  "amount": 1990000,
  "discount": 0,
  "method": "card",
  "installment_months": null,
  "schedule": null,
  "email": "student@example.com",
  "created_at": "2026-01-01T12:00:00"
}
```

### 3. Создать платёж с промокодом и рассрочкой

```bash
curl -s -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-key-2" \
  -d '{
    "tariff_id": 2,
    "method": "installment",
    "email": "student@example.com",
    "installment_months": 3,
    "promo_code": "KVITTO10"
  }'
```

Ответ (201 Created): `discount = 199000`, `amount = 1791000`,
`schedule = [597000, 597000, 597000]`.

### 4. Повторный запрос с тем же `Idempotency-Key`

Повторите команду из примера 2 ещё раз — придёт **200 OK** и тот же самый
платёж (второй не создаётся):

```bash
curl -s -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-key-1" \
  -d '{"tariff_id": 2, "method": "card", "email": "student@example.com"}'
```

### 5. Получить платёж по id

```bash
curl -s http://127.0.0.1:8000/payments/1
```

### 6. Список платежей с фильтрами

Без фильтров — вернёт **все** платежи, отсортированные по `id`:

```bash
curl -s http://127.0.0.1:8000/payments
```

Только платежи конкретного пользователя:

```bash
curl -s "http://127.0.0.1:8000/payments?email=student@example.com"
```

Только платежи в заданном статусе:

```bash
curl -s "http://127.0.0.1:8000/payments?status=succeeded"
```

Оба фильтра одновременно (условия объединяются через AND):

```bash
curl -s "http://127.0.0.1:8000/payments?email=student@example.com&status=succeeded"
```

Невалидный `email` или `status` → 422 от Pydantic:

```bash
curl -s "http://127.0.0.1:8000/payments?email=not-an-email"
curl -s "http://127.0.0.1:8000/payments?status=unknown"
```

Если ничего не найдено — вернётся `[]` с кодом 200.

### 7. Вебхук от банка

```bash
# pending → succeeded
curl -s -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" \
  -d '{"payment_id": 1, "status": "succeeded"}'
# → 200 {"result": "ok"}

# запрещённый переход (pending → refunded)
curl -s -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" \
  -d '{"payment_id": 1, "status": "refunded"}'
# → 409 {"detail": {"error": "invalid_transition"}}
```

### 8. Примеры для PowerShell

В PowerShell те же команды пишутся через `curl.exe --%` (всё после `--%`
передаётся программе как есть):

```powershell
curl.exe --% -s -X POST http://127.0.0.1:8000/payments -H "Content-Type: application/json" -H "Idempotency-Key: demo-key-1" -d "{\"tariff_id\": 2, \"method\": \"card\", \"email\": \"student@example.com\"}"
```

```powershell
curl.exe --% -s "http://127.0.0.1:8000/payments?email=student@example.com&status=succeeded"
```

Альтернатива — нативный для PowerShell `Invoke-RestMethod`:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/payments -Headers @{ "Idempotency-Key" = "demo-key-1" } -ContentType "application/json" -Body '{"tariff_id": 2, "method": "card", "email": "student@example.com"}'
```

## Бизнес-правила

- **Деньги** — только целые числа, в копейках (19 900 ₽ = 1 990 000).
- **Промокод** `KVITT010` — скидка 10% от цены тарифа, регистр не важен.
  Неизвестный код → 422.
- **Способы оплаты**: `card`, `sbp`, `installment`.
  Для `installment` обязателен `installment_months`: 3, 6 или 12.
- **График рассрочки** — сумма к оплате делится на равные части; «лишние»
  копейки уходят в первые платежи (сумма всех частей ровно равна `amount`).
- **Статусы**: новый платёж — `pending`.
  Разрешённые переходы: `pending → succeeded`, `pending → failed`,
  `succeeded → refunded`. Остальные — 409 `invalid_transition`.
- **Идемпотентность**: если передан `Idempotency-Key` и платёж с таким
  ключом уже есть — возвращается он же с кодом 200, новый не создаётся.
- **Список платежей** — `GET /payments` возвращает все платежи; можно
  отфильтровать по `email` (точное совпадение) и `status` (одно из
  `pending/succeeded/failed/refunded`). Невалидные значения → 422.

## Структура проекта

```
.
├── app/
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py       # engine, SessionLocal, Base, get_db
│   │   ├── init_db.py        # создание таблиц и засев тарифов при старте
│   │   └── models.py         # ORM-модели Tariff и Payment
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── payments.py       # POST /payments, GET /payments, GET /payments/{id}
│   │   ├── tariffs.py        # GET /tariffs
│   │   └── webhooks.py       # POST /webhooks/bank
│   ├── services/
│   │   ├── __init__.py
│   │   ├── payments.py       # расчёт скидки, суммы и графика рассрочки
│   │   └── statuses.py       # проверка допустимости перехода статуса
│   ├── constants.py          # тарифы, промокод, статусы, разрешённые переходы
│   ├── main.py               # создание FastAPI-приложения и подключение роутеров
│   └── schemas.py            # Pydantic-схемы запросов и ответов
├── docs_task/                # материалы задания
├── tests/
│   ├── conftest.py           # фикстура client: тестовая БД в памяти + подмена get_db
│   └── test_payments.py      # тесты платежей, тарифов, вебхуков и переходов
├── .gitignore
├── AI_LOG.md                 # отчёт о работе с ИИ
├── README.md
└── requirements.txt
```

## Эндпоинты

| Метод | Путь               | Описание                                                          |
|-------|--------------------|-------------------------------------------------------------------|
| GET   | `/tariffs`         | Список тарифов `{id, title, price}`                               |
| POST  | `/payments`        | Создать платёж (201) или вернуть существующий (200)               |
| GET   | `/payments`        | Список платежей; фильтры `?email=` и `?status=` (200, 422)        |
| GET   | `/payments/{id}`   | Получить платёж (200) или 404                                     |
| POST  | `/webhooks/bank`   | Смена статуса банком (200 / 404 / 409)                            |