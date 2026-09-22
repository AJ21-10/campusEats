from contextlib import contextmanager
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://campuseats:campuseats@localhost:5432/campuseats",
    )


@contextmanager
def connection():
    with psycopg.connect(database_url()) as conn:
        yield conn


@contextmanager
def transaction():
    with connection() as conn:
        with conn.transaction():
            yield conn


def fetch_one(query: str, params=()):
    with connection() as conn:
        return conn.execute(query, params).fetchone()


def fetch_all(query: str, params=()):
    with connection() as conn:
        return conn.execute(query, params).fetchall()


def check_connection() -> bool:
    with connection() as conn:
        conn.execute("SELECT 1")
    return True