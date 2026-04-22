from sqlmodel import create_engine, Session
from .models import SQLModel
from .config import settings

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.LOG_LEVEL == "DEBUG"
)

def get_session():
    with Session(engine) as session:
        yield session
