from contextlib import asynccontextmanager
from typing import AsyncGenerator

from gateway.firestore_store import FirestoreStore, store


async def get_db() -> AsyncGenerator[FirestoreStore, None]:
    yield store


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[FirestoreStore, None]:
    yield store
