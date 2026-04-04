from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import DeclarativeBase, MappedColumn
from sqlalchemy import MetaData

from gateway.config import settings

# Naming convention for constraints — required for Alembic autogenerate
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


def build_engine() -> AsyncEngine:
    connect_args = {}
    if "sqlite" in settings.DATABASE_URL:
        connect_args["check_same_thread"] = False
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        connect_args=connect_args,
    )


engine = build_engine()
