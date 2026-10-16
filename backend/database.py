import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = (
    f"postgresql+psycopg://{os.getenv('POSTGRES_USER', 'research_user')}:"
    f"{os.getenv('POSTGRES_PASSWORD', '')}@localhost:5432/"
    f"{os.getenv('POSTGRES_DB', 'research_chatbot')}"
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass
