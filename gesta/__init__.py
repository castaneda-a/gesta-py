# =============================================================================
# gesta/__init__.py
# =============================================================================
# Punto de entrada principal de la librería. Expone la API pública completa
# de Gesta — lo que el usuario necesita importar en su proyecto.
#
#   from gesta import Gesta
#   from gesta import WellnessStudio
#   from gesta import Person, Service, Appointment
#   from gesta import NotFoundError, ValidationError
# =============================================================================

from gesta.gesta import Gesta

# Extensiones
from gesta.extensions import WellnessStudio

# Entidades
from gesta.core import (
    Base,
    Person,
    Role,
    Offering,
    Service,
    Product,
    Appointment,
    Transaction,
    Payment,
)

# Enums
from gesta.core import (
    PaymentMethod,
    AppointmentStatus,
    TransactionStatus,
    OfferingType,
)

# Base de datos (uso común)
from gesta.core import (
    init_db,
    check_connection,
)

# Excepciones
from gesta.core import (
    GestaError,
    ValidationError,
    AppointmentConflictError,
    NotFoundError,
    DuplicateError,
    BusinessRuleError,
    UnpaidTransactionError,
    InactiveOfferingError,
    NoProviderError,
    InvalidRoleError,
    DatabaseError,
)

# Managers (acceso directo para usuarios avanzados)
from gesta.managers import (
    AppointmentManager,
    TransactionManager,
    PaymentManager,
    ReportManager,
)

# Dataclasses de reportes
from gesta.managers import (
    RevenueSummary,
    OfferingStats,
    PersonStats,
    AppointmentSummary,
)

__version__ = "0.1.0"

__all__ = [
    # Clase principal
    "Gesta",
    # Extensiones
    "WellnessStudio",
    # Entidades
    "Base",
    "Person",
    "Role",
    "Offering",
    "Service",
    "Product",
    "Appointment",
    "Transaction",
    "Payment",
    # Enums
    "PaymentMethod",
    "AppointmentStatus",
    "TransactionStatus",
    "OfferingType",
    # Base de datos
    "init_db",
    "check_connection",
    # Excepciones
    "GestaError",
    "ValidationError",
    "AppointmentConflictError",
    "NotFoundError",
    "DuplicateError",
    "BusinessRuleError",
    "UnpaidTransactionError",
    "InactiveOfferingError",
    "NoProviderError",
    "InvalidRoleError",
    "DatabaseError",
    # Managers
    "AppointmentManager",
    "TransactionManager",
    "PaymentManager",
    "ReportManager",
    # Reportes
    "RevenueSummary",
    "OfferingStats",
    "PersonStats",
    "AppointmentSummary",
    # Versión
    "__version__",
]