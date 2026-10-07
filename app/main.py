from fastapi import FastAPI

from app.database.init_db import init_db
from app.routers.tariffs import router as tariffs_router


app = FastAPI()

app.include_router(tariffs_router)


@app.on_event("startup")
def startup():
    init_db()