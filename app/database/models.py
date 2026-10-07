from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
# Подключаем типы данных дата + время, связь с другой таблицей, число, json, строка


from sqlalchemy.orm import Mapped, mapped_column
# нужно для описывания колонок бд
# Mapped - какой тип хранится указываем явно
# mapped_column - это настройки колонок, т.е. их параметры

from app.database.database import Base # загружаем ранее созданный нами ORM-модель

# class Tariff(Base) и class Payment(Base) - означают, что эти классы являются моделями таблиц БД
class Tariff(Base): # создаём ORM-модель таблицу тарифов.
    __tablename__ = "tariffs" # название таблицы

    id: Mapped[int] = mapped_column(Integer, primary_key=True) # айди_тарифа, primary_key - первичный ключ
    title: Mapped[str] = mapped_column(String, unique=True, nullable=False) # название_тарифа, unique=True -
    # означает что тарифы не могут иметь одинаковые названия, а nullable - название обязательно нельзя пустую строку
    price: Mapped[int] = mapped_column(Integer, nullable=False) # стоимость_тарифа


class Payment(Base): # таблица платежей
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True) # айди_платежа
    status: Mapped[str] = mapped_column(String, nullable=False) # статус_платежа

    tariff_id: Mapped[int] = mapped_column( # айди_тарифа которую купил пользователь,
        ForeignKey("tariffs.id"), # (таблица).(переменная_таблицы) как в postgresql - связываем таблицу
        # текущую с таблицей тарифов
        nullable=False,
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False) # итоговая сумма платежа с учётом скидки если была
    discount: Mapped[int] = mapped_column(Integer, nullable=False) # размер скидки за тариф благодаря коду

    method: Mapped[str] = mapped_column(String, nullable=False) # способ оплаты

    installment_months: Mapped[int | None] = mapped_column( # количество месяцев рассрочки если выбрали этот тип оплаты
        Integer,
        nullable=True,
    )

    schedule: Mapped[list[int] | None] = mapped_column( # график платежей по рассрочке, например 3 месяца:
        # [500000, 500000, 490000]
        JSON,
        nullable=True,
    )

    email: Mapped[str] = mapped_column(String, nullable=False) # почта покупателя

    created_at: Mapped[datetime] = mapped_column( # дата и время создания платежа
        DateTime,
        default=datetime.utcnow, # настройка означает, если при создании платежа не указали created_at (когда_создан)
        # тогда SQLAlchemy автоматически подберёт текущее UTC время
        nullable=False,
    )

    idempotency_key: Mapped[str | None] = mapped_column( # ключ защиты от повторного создания, который мы как-то
        # создавать будем или пользователь нам его отправит
        String,
        unique=True,
        nullable=True,
    )