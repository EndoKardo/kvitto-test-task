
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse # Нужен чтобы сделать вручную http ответ при "исключениях"
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
    status_code=status.HTTP_201_CREATED, # задаём статус код в случае успешного выполнения всего цикла (создания платежа)
)
def create_payment(
    payment: PaymentCreate,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None), # Берём ключ из заголовка
):
    # 1. Проверяем Idempotency-Key.
    # Если такой ключ уже есть — возвращаем существующий платёж.
    if idempotency_key is not None:
        existing_payment = db.scalar(
            select(Payment).where(
                Payment.idempotency_key == idempotency_key
            )
        ) # SELECT * from payments where idempotency_key = '{idempotency_key}'

        if existing_payment is not None:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=PaymentResponse.model_validate(
                    existing_payment
                ).model_dump(mode="json"),
            ) # Возвращаем json ответ и сообщаем о 200 что такой платёж уже есть с ключом и возвращаем информацию о платеже

    # 2. Находим тариф по tariff_id.
    tariff = db.get(Tariff, payment.tariff_id) # SELECT * from tariffs where id = '{payment.tariff_id}';

    if tariff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tariff not found",
        )

    # 3. Рассчитываем скидку по промокоду.
    try:
        discount = calc_discount( # подсчет скидки
            tariff.price, # цена выбранного тарифа
            payment.promo_code, # промокод
        )
    except UnknownPromoCodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown promo code",
        )

    # 4. Рассчитываем итоговую сумму.
    amount = calc_amount( # считаем итоговую стоимость тарифа со скидкой
        tariff.price, # стоимость тарифа
        discount, # скидка
    )

    # 5. Проверяем installment_months - количество месяцев рассрочки.
    installment_months = payment.installment_months
    schedule = None # переменная для создание списка рассрочки - плана платажей

    # Для card и sbp рассрочка не должна передаваться.
    if (
        payment.method != PaymentMethod.INSTALLMENT # проверяем что передаваемый метод не рассрочка
        and installment_months is not None # и если мы передаём вместе с другими методами оплаты не рассрочкой
            # кол-во месяцев для отсрочки тогда вызываем исключение и говорим что
            # рассрочка_месяцы передавать в запрос тогда тогда когда метод оплаты = рассрочке
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="installment_months is only allowed for installment",
        )

    # Для installment месяцы обязательны и могут быть только 3, 6 или 12.
    if payment.method == PaymentMethod.INSTALLMENT: # если метод оплаты рассрочка
        if installment_months is None: # если количество месяцев для рассрочки не указано
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="installment_months is required",
            )

        if installment_months not in INSTALLMENT_MONTHS: # если количество месяцев указанное в рассрочке не равно
            # 3, 6 или 12 месяцев срабатывает исключение
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="installment_months must be 3, 6 or 12",
            )

        schedule = build_schedule( # строим список и возвращаем его с количеством оплаты каждый месяц
            amount, # вся сумма к оплате за тариф
            installment_months, # кол-во месяцев для рассрочки на сколько делить всю оплату
        )

    # 6. Создаём новый платёж.
    new_payment = Payment( # Объект, который сразу понимает, что эта переменная является "частью" таблицы payments
        status=PaymentStatus.PENDING, # статус платежа pending - начальное состояние
        tariff_id=tariff.id, # выбранный тариф клиентом
        amount=amount, # итоговая сумма к оплате
        discount=discount, # скидка полученная благодаря промокоду
        method=payment.method, # метод оплаты
        installment_months=installment_months, # кол-во месяцев рассрочки если расрочка это метод оплаты иначе None
        schedule=schedule, # так же само как с кол-во месяцев рассрочки если не рассрочка нет информации сколько платить каждый месяц
        email=payment.email, # почта клиента
        idempotency_key=idempotency_key, # получения ключа чере загловок
    )

    # 7. Добавляем платёж в текущую сессию.
    db.add(new_payment) # И получается т.к. оно автоматически понимает, что new_payment = Payment() - это INSERT INTO
    # payments, тогда оставшайся структура имеет вид: INSERT INTO payments VALUES(...) и загружает данные в таблицу
    # Уточнение: он ещё её не вставил он как бы сделал пометку что нужно будет выполнить этот sql-запрос в момент commit

    # 8. Сохраняем изменения в БД.
    db.commit() # В ЭТОТ МОМЕНТ ключ, которого у нас не было записуется после commit в нашу переменную и в БД саму
    # после этого было new_payment.id = None, а по итогу стало new_payment.id = (следующий ключ доступный в момент
    # создания нового поля)

    # 9. Обновляем объект данными из БД.
    db.refresh(new_payment) # Т.е. по итогу мы возвращаем уже полноценно всю информацию о тарифе записанном в БД
    # после создания. Т.е. сначала мы создали как бы переменную - платежа, записали её и после записи появился ключ
    # И мы говорим что SELECT * from payments WHERE id = 7;

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

