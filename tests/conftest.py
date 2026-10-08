import pytest
from fastapi.testclient import TestClient # класс, который нужен чтобы можно было дать возможность
# отправлять HTTP-запросы к FastAPI-приложению прямо из Python-теста т.е. не нужно запускать сервер для тестов

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
# pool - механизм, который управляет подключениями к БД
# StaticPool - специальный тип пула, который использует одно и то же подключение к БД т.к. TEST_DATABASE_URL используем
# это SQLite в памяти, а не файл. Т.к. шняга такая если будет 2 подключения и в 1 мы создали таблицу, а 2 подключение
# попробует получить всю информации из таблицы он получит ответ, что такой таблицы не существует, т.к. 1 и 2 подключения
# это разные БД в памяти и они имеют разные состояния на момент создания которые не синхронизируются

from app.database.database import Base, get_db
from app.database.models import Tariff
from app.main import app


TEST_DATABASE_URL = "sqlite://" # означает, что используем SQLite, но не файл, а базу данных в памяти.

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# fixture - подготовка, которую pytest делает для теста. Т.е. сначала создаём переменные с которыми мы как бы работали
# бы создаём нужную среду для выполнения тестов
@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine) # создаём всю нашу БД в памяти, которую мы описали в файле models.py

    with Session(engine) as db: # создаём сессию для работы с бд
        db.add_all( # add_all() - это как add(), но add для 1, а add_all - позволяет создать сколько угодно обьектов
            # и записать их в БД (вернее дать команду запомнить что нужно их записать)
            [
                Tariff(title="basic", price=990_000),
                Tariff(title="standard", price=1_990_000),
                Tariff(title="premium", price=2_990_000),
            ]
        )
        db.commit()


    # АНАЛОГ нашей функции get_db() в init_db.py, когда тесты попросят get_db, вместо настоящего get_db дай ему
    # Session, работающую с тестовым engine
    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db # для этого приложения замени зависимость в кадом endpoints
    # get_db на override_get_db. Т.е. во время тестов мы говорим, что нужно использовать другую зависимость.
    # Мы делаем так, что словарь хранит в себе ссылку на функцию get_db и говорим, что не вызывай функцию get_db, а вызови
    # override_get_db().
    # КОРОЧЕ МЫ ГОВОРИМ ЧТО FastAPI ИСПОЛЬЗУЙ КЛЮЧ КАК ССЫЛКУ НА ФУНКЦИЮ СТАРУЮ И ЗА МЕСТО СТАРОЙ ДЛЯ ТЕСТОВ
    # ИСПОЛЬЗУЙ НОВУЮ ФУНКЦИЮ ВОТ ЭТУ

    with TestClient(app) as test_client: # Создаём тестового клиента который будет обращаться к нашим endopoint'ам
                                         # А также использует нами написанной свойство объекта, заменяя
                                         # db: Session = Depends(get_db) на db: Session = Depends(override_get_db)
        yield test_client # передаём подготовленный объект test_client тестам

    app.dependency_overrides.clear() # убираем подмену зависимости, которую мы делали для get_db
    Base.metadata.drop_all(bind=engine) # Удаляем таблицы очищаем всю БД