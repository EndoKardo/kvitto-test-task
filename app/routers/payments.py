
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import PaymentMethod, PaymentStatus, INSTALLMENT_MONTHS
from app.database.database import get_db
from app.database.models import Payment, Tariff
from app.schemas import PaymentCreate, PaymentResponse
from app.services.payments import (
    UnknownPromoCodeError,
    build_schedule,
    calc_amount,
    calc_discount,
)


router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    payment: PaymentCreate,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None),
):
    # 1. Проверяем Idempotency-Key.
    # Если такой ключ уже есть — возвращаем существующий платёж.
    if idempotency_key is not None:
        existing_payment = db.scalar(
            select(Payment).where(
                Payment.idempotency_key == idempotency_key
            )
        )

        if existing_payment is not None:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=PaymentResponse.model_validate(
                    existing_payment
                ).model_dump(mode="json"),
            )

    # 2. Находим тариф по tariff_id.
    tariff = db.get(Tariff, payment.tariff_id)

    if tariff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tariff not found",
        )

    # 3. Рассчитываем скидку по промокоду.
    try:
        discount = calc_discount(
            tariff.price,
            payment.promo_code,
        )
    except UnknownPromoCodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown promo code",
        )

    # 4. Рассчитываем итоговую сумму.
    amount = calc_amount(
        tariff.price,
        discount,
    )

    # 5. Проверяем installment_months.
    installment_months = payment.installment_months
    schedule = None

    # Для card и sbp рассрочка не должна передаваться.
    if (
        payment.method != PaymentMethod.INSTALLMENT
        and installment_months is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="installment_months is only allowed for installment",
        )

    # Для installment месяцы обязательны и могут быть только 3, 6 или 12.
    if payment.method == PaymentMethod.INSTALLMENT:
        if installment_months is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="installment_months is required",
            )

        if installment_months not in INSTALLMENT_MONTHS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="installment_months must be 3, 6 or 12",
            )

        schedule = build_schedule(
            amount,
            installment_months,
        )

    # 6. Создаём новый платёж.
    new_payment = Payment(
        status=PaymentStatus.PENDING,
        tariff_id=tariff.id,
        amount=amount,
        discount=discount,
        method=payment.method,
        installment_months=installment_months,
        schedule=schedule,
        email=payment.email,
        idempotency_key=idempotency_key,
    )

    # 7. Добавляем платёж в текущую сессию.
    db.add(new_payment)

    # 8. Сохраняем изменения в БД.
    db.commit()

    # 9. Обновляем объект данными из БД.
    db.refresh(new_payment)

    # 10. Возвращаем созданный платёж.
    return new_payment


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
):
    # Ищем платёж по его ID.
    payment = db.get(Payment, payment_id)

    # Если платежа нет — возвращаем 404.
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # Если нашли — возвращаем платёж.
    return payment

