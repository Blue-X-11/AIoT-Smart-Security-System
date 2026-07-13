from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import DateTime
from sqlalchemy import Text

from datetime import datetime

from app.db.database import Base


class PredictionRecord(Base):

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)

    filename = Column(String)

    prediction = Column(Text)

    source = Column(String)

    inference_time = Column(Float)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    username = Column(
        String,
        unique=True,
        nullable=False
    )

    email = Column(
        String,
        unique=True,
        nullable=False
    )

    password_hash = Column(
        String,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )