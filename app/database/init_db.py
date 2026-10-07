from sqlalchemy import select

from app.constants import TARIFFS
from app.database.database import Base, SessionLocal, engine
from app.database.models import Tariff


def init_db() -> None:

    # Создаём все таблицы, описанные через модели SQLAlchemy. Если уже всё создано мы просто
    # проверяем что все таблицы есть т.е. ничего не удаляем и не создаём
    Base.metadata.create_all(bind=engine)

    # Открываем сессию для работы с БД.
    db = SessionLocal()

    try:
        # Проверяем, есть ли уже тарифы в таблице tariffs. К таблице обращаемся по классу название таблицы
        existing_tariffs = db.scalars(select(Tariff)).all()
        # логика такая select(Tariff.id) - SELECT id FROM tariffs - выбрать только поле id
        # или select(Tariff) - взять всё из таблицы
        # .limit(1) - получаем 1 строку | .all() - получаем все записи
        # scalar() - взять первое значение из результата | slacars() - получить значения из результатов

        existing_titles = {tariff.title for tariff in existing_tariffs} # получаем названия тарифов
        # которые уже есть в бд

        # Проверяем каждый тариф из начального списка.
        for title, price in TARIFFS:
            # Если такого тарифа ещё нет в БД — добавляем его.
            if title not in existing_titles:
                db.add(
                    Tariff(
                        title=title,
                        price=price,
                    )
                ) # добавляет новое поле в таблице. В PostgreSQL это бы имело вид:
                # INSERT INTO tariffs (title, price) VALUES ('basic', 990000);

        db.commit()

    finally:
        # Закрываем сессию
        db.close()