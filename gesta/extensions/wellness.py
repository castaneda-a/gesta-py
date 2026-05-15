# =============================================================================
# extensions/wellness.py
# =============================================================================
# Extensión de Gesta para negocios de bienestar integral. Define los roles
# y servicios típicos de un centro de wellness: masajes, yoga, terapia, etc.
# Sirve como ejemplo concreto de cómo adaptar Gesta a un negocio específico.
# =============================================================================

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session, selectinload

from gesta.gesta import Gesta
from gesta.core.entities import Person, Role, Service, Product
from gesta.core.exceptions import NotFoundError, DuplicateError
from gesta.core.database import get_session


# ---------------------------------------------------------------------------
# Roles predefinidos del negocio de wellness
# ---------------------------------------------------------------------------

WELLNESS_ROLES = [
    {
        "id":           "role_client",
        "name":         "client",
        "description":  "Cliente que recibe servicios o compra productos.",
        "is_provider":  False,
        "is_recipient": True,
    },
    {
        "id":           "role_therapist",
        "name":         "therapist",
        "description":  "Terapeuta que imparte masajes y terapias corporales.",
        "is_provider":  True,
        "is_recipient": False,
    },
    {
        "id":           "role_instructor",
        "name":         "instructor",
        "description":  "Instructor que imparte clases grupales como yoga o meditación.",
        "is_provider":  True,
        "is_recipient": False,
    },
    {
        "id":           "role_admin",
        "name":         "admin",
        "description":  "Administrador del negocio. Puede ser proveedor y cliente.",
        "is_provider":  True,
        "is_recipient": True,
    },
]


# ---------------------------------------------------------------------------
# Servicios predefinidos de ejemplo
# ---------------------------------------------------------------------------

WELLNESS_SERVICES = [
    {
        "id":               "svc_masaje_sueco",
        "name":             "Masaje sueco",
        "description":      "Masaje relajante de cuerpo completo.",
        "price":            Decimal("600.00"),
        "cost":             Decimal("150.00"),
        "duration_minutes": "60",
        "requires_provider": True,
    },
    {
        "id":               "svc_masaje_piedras",
        "name":             "Masaje con piedras calientes",
        "description":      "Masaje terapéutico con piedras volcánicas.",
        "price":            Decimal("800.00"),
        "cost":             Decimal("200.00"),
        "duration_minutes": "75",
        "requires_provider": True,
    },
    {
        "id":               "svc_yoga_grupal",
        "name":             "Clase de yoga grupal",
        "description":      "Clase de yoga para grupos de hasta 15 personas.",
        "price":            Decimal("120.00"),
        "cost":             Decimal("300.00"),
        "duration_minutes": "60",
        "requires_provider": True,
    },
    {
        "id":               "svc_meditacion",
        "name":             "Sesión de meditación",
        "description":      "Sesión guiada de meditación y mindfulness.",
        "price":            Decimal("100.00"),
        "cost":             Decimal("200.00"),
        "duration_minutes": "45",
        "requires_provider": True,
    },
    {
        "id":               "svc_terapia",
        "name":             "Terapia holística",
        "description":      "Sesión individual de terapia holística.",
        "price":            Decimal("900.00"),
        "cost":             Decimal("250.00"),
        "duration_minutes": "90",
        "requires_provider": True,
    },
]


# ---------------------------------------------------------------------------
# Productos predefinidos de ejemplo
# ---------------------------------------------------------------------------

WELLNESS_PRODUCTS = [
    {
        "id":              "prd_aceite_lavanda",
        "name":            "Aceite esencial de lavanda",
        "description":     "Aceite esencial 100% puro, 10ml.",
        "price":           Decimal("180.00"),
        "cost":            Decimal("60.00"),
        "stock":           Decimal("50"),
        "track_inventory": True,
    },
    {
        "id":              "prd_incienso",
        "name":            "Incienso sándalo",
        "description":     "Paquete de 20 varillas de incienso de sándalo.",
        "price":           Decimal("80.00"),
        "cost":            Decimal("25.00"),
        "stock":           Decimal("100"),
        "track_inventory": True,
    },
    {
        "id":              "prd_vela",
        "name":            "Vela aromática",
        "description":     "Vela de soya con aromas naturales, 200g.",
        "price":           Decimal("220.00"),
        "cost":            Decimal("70.00"),
        "stock":           Decimal("30"),
        "track_inventory": True,
    },
    {
        "id":              "prd_hierbas",
        "name":            "Mix de hierbas relajantes",
        "description":     "Mezcla de hierbas para infusión relajante, 50g.",
        "price":           Decimal("120.00"),
        "cost":            Decimal("30.00"),
        "stock":           Decimal("40"),
        "track_inventory": True,
    },
]


# =============================================================================
# WellnessStudio
# =============================================================================

class WellnessStudio(Gesta):
    """
    Extensión de Gesta para centros de bienestar integral.

    Precarga roles, servicios y productos típicos del negocio.
    Agrega métodos de conveniencia específicos para wellness.

    Uso:
        studio = WellnessStudio(db_url="sqlite:///wellness.db")
        studio.setup()   ← carga roles, servicios y productos iniciales

        with studio.session() as s:
            cliente = studio.add_client(s, name="Ana García", phone="5551234567")
            terapeuta = studio.add_provider(s, name="Luis Ramos", role="therapist")
    """

    def __init__(self, db_url: str, echo: bool = False):
        super().__init__(db_url=db_url, echo=echo)

    # -----------------------------------------------------------------------
    # Setup inicial
    # -----------------------------------------------------------------------

    def setup(self, load_sample_data: bool = True) -> None:
        """
        Inicializa el negocio cargando roles predefinidos y,
        opcionalmente, los servicios y productos de ejemplo.

        Es seguro llamarlo múltiples veces — no duplica registros.

        load_sample_data=False carga solo los roles, sin servicios
        ni productos de ejemplo. Útil para producción.
        """
        with self.session() as s:
            self._ensure_roles(s)
            if load_sample_data:
                self._ensure_services(s)
                self._ensure_products(s)

    def _ensure_roles(self, session: Session) -> None:
        """Crea los roles si no existen."""
        for role_data in WELLNESS_ROLES:
            existing = session.get(Role, role_data["id"])
            if not existing:
                role = Role(**role_data)
                session.add(role)

    def _ensure_services(self, session: Session) -> None:
        """Crea los servicios de ejemplo si no existen."""
        from gesta.core.entities import OfferingType
        for svc_data in WELLNESS_SERVICES:
            existing = session.get(Service, svc_data["id"])
            if not existing:
                svc = Service(
                    type = OfferingType.SERVICE,
                    **svc_data,
                )
                session.add(svc)

    def _ensure_products(self, session: Session) -> None:
        """Crea los productos de ejemplo si no existen."""
        from gesta.core.entities import OfferingType
        for prd_data in WELLNESS_PRODUCTS:
            existing = session.get(Product, prd_data["id"])
            if not existing:
                prd = Product(
                    type = OfferingType.PRODUCT,
                    **prd_data,
                )
                session.add(prd)

    # -----------------------------------------------------------------------
    # Helpers de personas
    # -----------------------------------------------------------------------

    def _get_role_or_raise(self, session: Session, role_name: str) -> Role:
        role = session.query(Role).filter(Role.name == role_name).first()
        if not role:
            raise NotFoundError("Role", role_name)
        return role

    def _person_exists(self, session: Session, email: str) -> bool:
        if not email:
            return False
        return session.query(Person).filter(Person.email == email).first() is not None

    def add_client(
        self,
        session: Session,
        name: str,
        phone: str = None,
        email: str = None,
        notes: str = None,
    ) -> Person:
        """
        Registra una nueva persona con rol 'client'.
        Lanza DuplicateError si el email ya existe.
        """
        if email and self._person_exists(session, email):
            raise DuplicateError("Person", "email", email)

        role   = self._get_role_or_raise(session, "client")
        person = Person(
            id    = str(uuid.uuid4()),
            name  = name,
            phone = phone,
            email = email,
            notes = notes,
        )
        person.roles = [role]
        session.add(person)
        return person

    def add_provider(
        self,
        session: Session,
        name: str,
        role: str,
        phone: str = None,
        email: str = None,
        notes: str = None,
    ) -> Person:
        """
        Registra una nueva persona con un rol de proveedor.
        role debe ser 'therapist', 'instructor' o 'admin'.
        Lanza DuplicateError si el email ya existe.
        """
        if email and self._person_exists(session, email):
            raise DuplicateError("Person", "email", email)

        role_obj = self._get_role_or_raise(session, role)

        if not role_obj.is_provider:
            from gesta.core.exceptions import InvalidRoleError
            raise InvalidRoleError(name, role)

        person = Person(
            id    = str(uuid.uuid4()),
            name  = name,
            phone = phone,
            email = email,
            notes = notes,
        )
        person.roles = [role_obj]
        session.add(person)
        return person

    def get_person(self, session: Session, person_id: str) -> Person:
        """Retorna una persona por ID o lanza NotFoundError."""
        person = session.get(Person, person_id)
        if not person:
            raise NotFoundError("Person", person_id)
        return person

    def list_clients(self, session: Session) -> list[Person]:
        """Retorna todas las personas con rol client."""
        return (
            session.query(Person)
            .options(selectinload(Person.roles))
            .filter(Person.roles.any(Role.name == "client"))
            .order_by(Person.name)
            .all()
        )

    def list_providers(self, session: Session) -> list[Person]:
        """Retorna todas las personas con rol proveedor activas."""
        return (
            session.query(Person)
            .options(selectinload(Person.roles))
            .filter(Person.roles.any(Role.is_provider == True))
            .order_by(Person.name)
            .all()
        )