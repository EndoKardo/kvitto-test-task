from sqlalchemy import select

from app.constants import TARIFFS
from app.database.database import Base, SessionLocal, engine
from app.database.models import Tariff


def init_db() -> None:
    # Создаём все таблицы, описанные через модели SQLAlchemy.
    Base.metadata.create_all(bind=engine)

    # Открываем сессию для работы с БД.
    db = SessionLocal()

    try:
        # Проверяем, есть ли уже тарифы в таблице tariffs.
        tariffs_exist = db.scalar(select(Tariff.id).limit(1))

        # Если тарифов ещё нет — добавляем начальные.
        if tariffs_exist is None:
            db.add_all(
                [
                    Tariff(title=title, price=price)
                    for title, price in TARIFFS
                ]
            )
            db.commit()
    finally:
        # В любом случае закрываем сессию.
        db.close()