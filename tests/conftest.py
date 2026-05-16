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
    AppointmentStatus, TransactionStatus,
)


# ---------------------------------------------------------------------------
# BD y sesión
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    engine = create_db_engine("sqlite:///:memory:", echo=False)
    init_db(engine)
    return engine


@pytest.fixture(scope="function")
def session(engine):
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
    client_role = Role(
        id           = "role_client",
        name         = "client",
    )
    therapist_role = Role(
        id           = "role_therapist",
        name         = "therapist",
    )
    instructor_role = Role(
        id           = "role_instructor",
        name         = "instructor",
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
    person = Person(
        id           = "person_ana",
        name         = "Ana García",
        email        = "ana@mail.com",
        phone        = "5551234567",
        is_provider  = False,
        is_recipient = True,
    )
    person.roles = [roles["client"]]
    session.add(person)
    session.flush()
    return person


@pytest.fixture
def client_luis(session, roles):
    person = Person(
        id           = "person_luis",
        name         = "Luis Ramos",
        email        = "luis@mail.com",
        is_provider  = False,
        is_recipient = True,
    )
    person.roles = [roles["client"]]
    session.add(person)
    session.flush()
    return person


@pytest.fixture
def therapist_marta(session, roles):
    person = Person(
        id           = "person_marta",
        name         = "Marta López",
        email        = "marta@mail.com",
        is_provider  = True,
        is_recipient = False,
    )
    person.roles = [roles["therapist"]]
    session.add(person)
    session.flush()
    return person


@pytest.fixture
def instructor_pedro(session, roles):
    person = Person(
        id           = "person_pedro",
        name         = "Pedro Soto",
        email        = "pedro@mail.com",
        is_provider  = True,
        is_recipient = False,
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
    service = Service(
        id               = "svc_masaje",
        name             = "Masaje sueco",
        price            = Decimal("600.00"),
        cost             = Decimal("150.00"),
        duration_min     = 60,
        requires_space   = True,
        is_active        = True,
    )
    session.add(service)
    session.flush()
    return service


@pytest.fixture
def service_yoga(session):
    service = Service(
        id               = "svc_yoga",
        name             = "Clase de yoga",
        price            = Decimal("120.00"),
        cost             = Decimal("300.00"),
        duration_min     = 60,
        requires_space   = True,
        is_active        = True,
    )
    session.add(service)
    session.flush()
    return service


@pytest.fixture
def product_aceite(session):
    product = Product(
        id             = "prd_aceite",
        name           = "Aceite de lavanda",
        price          = Decimal("180.00"),
        cost           = Decimal("60.00"),
        stock          = 50,
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
    return datetime.now() + timedelta(days=7)


@pytest.fixture
def past_date():
    return datetime.now() - timedelta(days=1)