# =============================================================================
# gesta.py
# =============================================================================
# Clase principal que orquesta todos los componentes de la librería.
# Es el único punto de entrada que el usuario necesita instanciar.
# Crea el engine, inicializa la BD, y expone los managers como atributos.
#
#   from gesta.gesta import Gesta
#   studio = Gesta(db_url="sqlite:///negocio.db")
#   studio.appointments.book(...)
#   studio.transactions.register(...)
# =============================================================================

from sqlalchemy.orm import sessionmaker

from gesta.core.database import (
    create_db_engine,
    create_session_factory,
    get_session,
    init_db,
    check_connection,
)
from gesta.core.exceptions import DatabaseError
from gesta.managers.calendar import AppointmentManager
from gesta.managers.transactions import TransactionManager, PaymentManager
from gesta.managers.reports import ReportManager


class Gesta:
    """
    Punto de entrada principal de la librería.

    Instancia el engine, inicializa las tablas y expone los managers
    como atributos. Cada operación que toca la BD se ejecuta dentro
    de un context manager de sesión que garantiza commit/rollback.

    Parámetros:
        db_url  — URL de conexión a la base de datos.
                  SQLite:   'sqlite:///mi_negocio.db'
                  Memoria:  'sqlite:///:memory:'
                  Postgres: 'postgresql://user:pass@localhost/gesta'
        echo    — Si True, imprime el SQL generado. Útil en desarrollo.

    Uso básico:
        studio = Gesta(db_url="sqlite:///negocio.db")

        with studio.session() as s:
            appt = studio.appointments(s).book(
                service_id   = "srv1",
                client_ids   = ["cli1"],
                provider_ids = ["pro1"],
                scheduled_at = datetime(2025, 6, 1, 10, 0),
            )
    """

    def __init__(self, db_url: str, echo: bool = False):
        self._engine          = create_db_engine(db_url, echo=echo)
        self._session_factory = create_session_factory(self._engine)
        self._initialize()

    # -----------------------------------------------------------------------
    # Inicialización
    # -----------------------------------------------------------------------

    def _initialize(self) -> None:
        """Verifica la conexión e inicializa las tablas."""
        if not check_connection(self._engine):
            raise DatabaseError(
                "No se pudo conectar a la base de datos. "
                "Verifica la URL de conexión."
            )
        init_db(self._engine)

    # -----------------------------------------------------------------------
    # Sesión
    # -----------------------------------------------------------------------

    def session(self):
        """
        Context manager que provee una sesión de BD.
        Hace commit automático al salir, rollback si hay excepción.

        Uso:
            with studio.session() as s:
                studio.appointments(s).book(...)
                studio.transactions(s).register(...)
                # ambas operaciones se confirman juntas
        """
        return get_session(self._session_factory)

    # -----------------------------------------------------------------------
    # Managers
    # -----------------------------------------------------------------------

    def appointments(self, session) -> AppointmentManager:
        """Retorna el manager de citas ligado a la sesión dada."""
        return AppointmentManager(session)

    def transactions(self, session) -> TransactionManager:
        """Retorna el manager de transacciones ligado a la sesión dada."""
        return TransactionManager(session)

    def payments(self, session) -> PaymentManager:
        """Retorna el manager de pagos ligado a la sesión dada."""
        return PaymentManager(session)

    def reports(self, session) -> ReportManager:
        """Retorna el manager de reportes ligado a la sesión dada."""
        return ReportManager(session)

    # -----------------------------------------------------------------------
    # Utilidades
    # -----------------------------------------------------------------------

    def ping(self) -> bool:
        """Verifica que la base de datos siga accesible."""
        return check_connection(self._engine)

    def __repr__(self):
        return f"<Gesta engine={self._engine.url!r}>"