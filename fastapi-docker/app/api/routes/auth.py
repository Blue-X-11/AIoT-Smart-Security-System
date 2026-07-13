from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import User

from app.schemas.user import UserCreate

from app.core.auth import hash_password
from app.schemas.user import UserLogin

from app.core.auth import verify_password
from app.core.auth import create_access_token

router = APIRouter()

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()

@router.post("/register")
def register(
    user: UserCreate,
    db: Session = Depends(get_db)
):

    existing_user = db.query(User).filter(
        User.username == user.username
    ).first()

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    existing_email = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_email:

        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    hashed_password = hash_password(
        user.password
    )

    new_user = User(
        username=user.username,
        email=user.email,
        password_hash=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User registered successfully",
        "user_id": new_user.id
    }

@router.post("/login")
def login(
    user: UserLogin,
    db: Session = Depends(get_db)
):

    db_user = db.query(User).filter(
        User.username == user.username
    ).first()

    if not db_user:

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not verify_password(
        user.password,
        db_user.password_hash
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    token = create_access_token(
        {"sub": db_user.username}
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }