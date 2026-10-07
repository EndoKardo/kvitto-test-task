from fastapi import APIRouter, Depends, HTTPException, status
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
    payment = db.get(Payment, webhook.payment_id)

    # Если платежа нет — 404.
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # 2. Проверяем, разрешён ли переход статуса.
    if not can_transition(
        payment.status,
        webhook.status,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "invalid_transition",
            },
        )

    # 3. Меняем статус платежа.
    payment.status = webhook.status

    # 4. Сохраняем изменение в БД.
    db.commit()

    # 5. Сообщаем банку об успешной обработке.
    return {"result": "ok"}