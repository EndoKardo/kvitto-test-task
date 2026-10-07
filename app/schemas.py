from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr
# BaseModel — базовый класс Pydantic-моделей.
# ConfigDict — настройки Pydantic-модели.
# EmailStr — специальный тип Pydantic для проверки email.


from app.constants import PaymentMethod, PaymentStatus # импортируем наши константы метода_оплаты и статуса_оплаты


# для POST /payments - создание оплаты, т.е. получение данных, которые клиент отправляет нам при создании платежа
class PaymentCreate(BaseModel):
    tariff_id: int # айди_тарифа который покупает клиент
    method: PaymentMethod # метод_оплаты
    email: EmailStr # почта_клиента
    promo_code: str | None = None # промокод на скидку или без промокода
    installment_months: int | None = None # количество месяцев расрочки если пользователь выбрал расрочку как метод_оплаты


# то, что API возвращает после создания/получения платежа, т.е. нужен для ответа POST /payments и GET /payments/{id}
class PaymentResponse(BaseModel):
    id: int # айди_созданного_платежа
    status: PaymentStatus # статус_платежа
    tariff_id: int # айди_тарифа
    amount: int #итоговая_сумма_с_учётом_скидки
    discount: int #размер_скидки
    method: PaymentMethod # метод_оплаты
    installment_months: int | None # количество_месяцев_рассрочки
    schedule: list[int] | None # график_платежей
    email: EmailStr # почта_клиента
    created_at: datetime # когда_создан

    model_config = ConfigDict(from_attributes=True) # эта строка означает, что мы разрешаем создавать PaymentResponse
    # не только из обычного dict, но и из объекта SQLAlchemy
    # Т.е. Pydantic возьмёт значения прямо из атрибутов SQLAlchemy-объекта.


# для POST /webhooks/bank - данные которые банк отправляем клиентам, чтоб оповестить об изменении статуса платежа
class BankWebhook(BaseModel):
    payment_id: int # айди_платежа который изменился
    status: PaymentStatus # статус_платежа на который изменился т.е. его новый статус