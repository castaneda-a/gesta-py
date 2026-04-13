# =============================================================================
# managers/__init__.py
# =============================================================================
# Expone la API pública del módulo managers. Permite importar los managers
# directamente desde gesta.managers en lugar de conocer en qué archivo
# vive cada uno.
#
#   from gesta.managers import AppointmentManager, TransactionManager
# =============================================================================

from gesta.managers.calendar import AppointmentManager
from gesta.managers.transactions import TransactionManager, PaymentManager
from gesta.managers.reports import (
    ReportManager,
    RevenueSummary,
    OfferingStats,
    PersonStats,
    AppointmentSummary,
)

__all__ = [
    # Managers
    "AppointmentManager",
    "TransactionManager",
    "PaymentManager",
    "ReportManager",
    # Dataclasses de resultados
    "RevenueSummary",
    "OfferingStats",
    "PersonStats",
    "AppointmentSummary",
]