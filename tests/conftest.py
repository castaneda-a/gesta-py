# =============================================================================
# tests/conftest.py
# =============================================================================
# Fixtures compartidos para todos los tests. Configura la BD en memoria,
# la sesión, y datos base reutilizables como roles, servicios y personas.
# =============================================================================

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from gesta.core.database import create_db_engine, create_session_factory, init_db
from gesta.core.entities import (
    Person, Role, Service, Product,
    OfferingType, AppointmentStatus, TransactionStatus,
)


# ---------------------------------------------------------------------------
# BD y sesión
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    """
    Engine SQLite en memoria compartido por toda la sesión de tests.
    scope="session" significa que se crea una sola vez para todos los tests.
    """
    engine = create_db_engine("sqlite:///:memory:", echo=False)
    init_db(engine)
    return engine


@pytest.fixture(scope="function")
def session(engine):
    """
    Sesión de BD limpia para cada test.
    Usa rollback al final para que cada test empiece con BD vacía.
    """
    factory    = create_session_factory(engine)
    db_session = factory()
    yield db_session
    db_session.rollback()
    db_session.close()


# ---------------------------------------------------------------------------
# Roles base
# ---------------------------------------------------------------------------

@pytest.fixture
def roles(session):
    """Crea y retorna los roles básicos de wellness."""
    client_role = Role(
        id           = "role_client",
        name         = "client",
        is_provider  = False,
        is_recipient = True,
    )
    therapist_role = Role(
        id           = "role_therapist",
        name         = "therapist",
        is_provider  = True,
        is_recipient = False,
    )
    instructor_role = Role(
        id           = "role_instructor",
        name         = "instructor",
        is_provider  = True,
        is_recipient = False,
    )

    session.add_all([client_role, therapist_role, instructor_role])
    session.flush()

    return {
        "client":     client_role,
        "therapist":  therapist_role,
        "instructor": instructor_role,
    }


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------

@pytest.fixture
def client_ana(session, roles):
    """Persona con rol client."""
    person = Person(
        id    = "person_ana",
        name  = "Ana García",
        email = "ana@mail.com",
        phone = "5551234567",
    )
    person.roles = [roles["client"]]
    session.add(person)
    session.flush()
    return person


@pytest.fixture
def client_luis(session, roles):
    """Segunda persona con rol client — para tests grupales."""
    person = Person(
        id    = "person_luis",
        name  = "Luis Ramos",
        email = "luis@mail.com",
    )
    person.roles = [roles["client"]]
    session.add(person)
    session.flush()
    return person


@pytest.fixture
def therapist_marta(session, roles):
    """Persona con rol therapist."""
    person = Person(
        id    = "person_marta",
        name  = "Marta López",
        email = "marta@mail.com",
    )
    person.roles = [roles["therapist"]]
    session.add(person)
    session.flush()
    return person


@pytest.fixture
def instructor_pedro(session, roles):
    """Persona con rol instructor."""
    person = Person(
        id    = "person_pedro",
        name  = "Pedro Soto",
        email = "pedro@mail.com",
    )
    person.roles = [roles["instructor"]]
    session.add(person)
    session.flush()
    return person


# ---------------------------------------------------------------------------
# Offerings
# ---------------------------------------------------------------------------

@pytest.fixture
def service_masaje(session):
    """Servicio de masaje sueco — requiere proveedor, 60 min."""
    service = Service(
        id               = "svc_masaje",
        type             = OfferingType.SERVICE,
        name             = "Masaje sueco",
        price            = Decimal("600.00"),
        cost             = Decimal("150.00"),
        duration_minutes = "60",
        requires_provider = True,
        is_active        = True,
    )
    session.add(service)
    session.flush()
    return service


@pytest.fixture
def service_yoga(session):
    """Servicio de yoga grupal — requiere proveedor, 60 min."""
    service = Service(
        id               = "svc_yoga",
        type             = OfferingType.SERVICE,
        name             = "Clase de yoga",
        price            = Decimal("120.00"),
        cost             = Decimal("300.00"),
        duration_minutes = "60",
        requires_provider = True,
        is_active        = True,
    )
    session.add(service)
    session.flush()
    return service


@pytest.fixture
def product_aceite(session):
    """Producto de aceite esencial."""
    product = Product(
        id             = "prd_aceite",
        type           = OfferingType.PRODUCT,
        name           = "Aceite de lavanda",
        price          = Decimal("180.00"),
        cost           = Decimal("60.00"),
        stock          = Decimal("50"),
        track_inventory = True,
        is_active      = True,
    )
    session.add(product)
    session.flush()
    return product


# ---------------------------------------------------------------------------
# Fechas de utilidad
# ---------------------------------------------------------------------------

@pytest.fixture
def future_date():
    """Fecha en el futuro — para citas válidas."""
    return datetime.now() + timedelta(days=7)


@pytest.fixture
def past_date():
    """Fecha en el pasado — para tests de validación."""
    return datetime.now() - timedelta(days=1)