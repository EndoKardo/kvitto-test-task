from fastapi import FastAPI

from app.database.init_db import init_db
from app.routers.tariffs import router as tariffs_router
from app.routers.payments import router as payments_router
from app.routers.webhooks import router as webhooks_router


app = FastAPI()

app.include_router(tariffs_router) # 200 - запрос успешно обработан, данные успешно отправлены

app.include_router(payments_router)

app.include_router(webhooks_router)


@app.on_event("startup")
def startup():
    init_db()