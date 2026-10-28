from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import create_db_engine, create_session_factory
from app.models import User


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATA_DIR / 'badminton.db'}"

engine = create_db_engine(DATABASE_URL)
SessionLocal = create_session_factory(engine)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        yield db


def get_now() -> datetime:
    return datetime.now(timezone.utc)


DatabaseSession = Annotated[Session, Depends(get_db)]
DemoUserId = Annotated[str | None, Header(alias="X-Demo-User-Id")]
CurrentTime = Annotated[datetime, Depends(get_now)]


def get_current_user(
    db: DatabaseSession,
    x_demo_user_id: DemoUserId = None,
) -> User:
    if not x_demo_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Demo user identity is required",
        )

    user = db.get(User, x_demo_user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Demo user identity is invalid",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
