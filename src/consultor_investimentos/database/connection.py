from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

import os

_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/investimentos.db")

# Para paths relativos com SQLite, resolve em relação à raiz do projeto
if _DATABASE_URL.startswith("sqlite:///./"):
    _relative_path = _DATABASE_URL.removeprefix("sqlite:///./")
    _project_root = Path(__file__).parent.parent.parent.parent
    _db_path = _project_root / _relative_path
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    _DATABASE_URL = f"sqlite:///{_db_path}"

engine = create_engine(
    _DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """Ativa foreign keys no SQLite — desativado por padrão."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


@contextmanager
def get_db() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Cria todas as tabelas se não existirem. Usado apenas em desenvolvimento."""
    from consultor_investimentos.database import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
