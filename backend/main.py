from fastapi import FastAPI
from sqlalchemy import text
from backend.database import engine

app = FastAPI(title="Research Paper Chatbot")


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
def database_health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"database": "connected"}
