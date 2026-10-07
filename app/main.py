from fastapi import FastAPI

from app.database.init_db import init_db


app = FastAPI()


@app.on_event("startup")
def startup():
    init_db()