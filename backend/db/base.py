"""Declarative base for all ORM models. Alembic reads Base.metadata"""

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass