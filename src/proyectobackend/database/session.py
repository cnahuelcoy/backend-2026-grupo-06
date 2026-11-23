import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./taller_mecanico.db",
)

connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

def configurar_minusculas_sqlite(conexion, registro) -> None:
    conexion.create_function(
        "lower", 1,
        lambda valor: valor.lower() if valor is not None else None,
        deterministic=True,
    )


if engine.dialect.name == "sqlite":
    event.listen(engine, "connect", configurar_minusculas_sqlite)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)
