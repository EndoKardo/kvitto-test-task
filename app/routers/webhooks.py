from fastapi import APIRouter, Depends, HTTPException, status
# HTTPException - импорт для остановки эндпоинтов с возвратом клиенту http-ошибки
# status - это набор готовых констант http-кодов
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Payment
from app.schemas import BankWebhook
from app.services.statuses import can_transition


router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
)


@router.post("/bank")
def bank_webhook(
    webhook: BankWebhook,
    db: Session = Depends(get_db),
):
    # 1. Ищем платёж по payment_id.
    payment = db.get(Payment, webhook.payment_id) # Select * from payments where id={webhook.payment_id}.
    # Поиск происходит по ключу т.к. get() предназначен для поиска по главному ключу primary_key
    # Чтобы найти платёж по какому-то другому фильтру используется конструкция:
    # payment = db.scalar(
    #     select(Payment).where(
    #         Payment.email == "test@example.com"
    #     )
    # )
    # Это как: SELECT * FROM payments WHERE email = 'test@example.com';

    # Если платежа нет вызываем ошибку 404.
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # 2. Проверяем, разрешён ли переход статуса.
    if not can_transition(
        payment.status, # старый статус платежа
        webhook.status, # новый статус платежа
    ):
        raise HTTPException( # вызываем ошибку невозможности смены статуса
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "invalid_transition",
            },
        )

    # 3. Меняем статус платежа.
    payment.status = webhook.status
    # Здесь мы поменяли статус старый на новый и он как бы выполнил команду UPDATE автоматически
    # UPDATE payments SET status = '{webhook.status}' where id = {webhook.payment_id};

    # 4. Сохраняем изменение в БД.
    db.commit()

    # 5. Сообщаем банку об успешной обработке.
    return {"result": "ok"}