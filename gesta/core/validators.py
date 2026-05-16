# =============================================================================
# validators.py
# =============================================================================
# Contiene funciones de validación reutilizables que los managers invocan antes
# de escribir a la BD. Por ejemplo: verificar que una fecha no sea en el
# pasado, que un precio sea positivo, que un horario no se traslape con otro
# existente. Separadas de los managers para poder reutilizarlas y testearlas
# independientemente.
# =============================================================================

from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session

from gesta.core.exceptions import (
    ValidationError,
    AppointmentConflictError,
    NoProviderError,
    InvalidRoleError,
    InactiveOfferingError,
)
from gesta.core.entities import Appointment, AppointmentStatus


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------

def validate_future_datetime(dt: datetime, field_name: str = "fecha") -> None:
    if dt <= datetime.now():
        raise ValidationError(
            f"El campo {field_name!r} debe ser una fecha y hora futura. "
            f"Se recibió: {dt}"
        )


def validate_datetime_range(start: datetime, end: datetime) -> None:
    if start >= end:
        raise ValidationError(
            f"La fecha de inicio ({start}) debe ser anterior "
            f"a la fecha de fin ({end})."
        )


# ---------------------------------------------------------------------------
# Precios y montos
# ---------------------------------------------------------------------------

def validate_positive_amount(amount: Decimal, field_name: str = "monto") -> None:
    if amount <= Decimal("0"):
        raise ValidationError(
            f"El campo {field_name!r} debe ser mayor a cero. "
            f"Se recibió: {amount}"
        )


def validate_payment_does_not_exceed_balance(
    payment_amount: Decimal,
    current_balance: Decimal,
) -> None:
    if payment_amount > current_balance:
        raise ValidationError(
            f"El monto del pago ({payment_amount}) excede el balance "
            f"pendiente de la transacción ({current_balance})."
        )


# ---------------------------------------------------------------------------
# Campos requeridos
# ---------------------------------------------------------------------------

def validate_required_string(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValidationError(
            f"El campo {field_name!r} es requerido y no puede estar vacío."
        )


def validate_required_list(value: list, field_name: str) -> None:
    if not value:
        raise ValidationError(
            f"El campo {field_name!r} debe contener al menos un elemento."
        )


# ---------------------------------------------------------------------------
# Offerings
# ---------------------------------------------------------------------------

def validate_offering_is_active(item) -> None:
    """
    Verifica que un servicio o producto esté activo.
    """
    if not getattr(item, 'is_active', True):
        raise InactiveOfferingError(item.name)


def validate_service_has_provider(
    service,
    providers: list,
) -> None:
    """
    Verifica que un servicio tenga al menos un proveedor asignado.
    """
    if not providers:
        raise NoProviderError(service.name)

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

def validate_persons_are_recipients(persons: list) -> None:
    for person in persons:
        if not person.is_recipient:
            raise InvalidRoleError(person.name, "recipient")


def validate_persons_are_providers(persons: list) -> None:
    for person in persons:
        if not person.is_provider:
            raise InvalidRoleError(person.name, "provider")


# ---------------------------------------------------------------------------
# Conflictos de agenda
# ---------------------------------------------------------------------------

def validate_no_schedule_conflict(
    session: Session,
    provider_ids: list[str],
    scheduled_at: datetime,
    duration_minutes: int,
    exclude_appointment_id: str = None,
) -> None:
    from datetime import timedelta

    end_time = scheduled_at + timedelta(minutes=duration_minutes)

    existing: list[Appointment] = (
        session.query(Appointment)
        .filter(
            Appointment.status == AppointmentStatus.SCHEDULED,
        )
        .all()
    )

    for appt in existing:
        if exclude_appointment_id and appt.id == exclude_appointment_id:
            continue

        if appt.service is None or appt.service.duration_min is None:
            continue

        appt_end = appt.scheduled_at + timedelta(
            minutes=int(appt.service.duration_min)
        )

        if scheduled_at < appt_end and end_time > appt.scheduled_at:
            conflicting_providers = [
                p.id for p in appt.persons if p.is_provider and p.id in provider_ids
            ]
            if conflicting_providers:
                raise AppointmentConflictError(
                    f"Conflicto de horario: uno o más proveedores ya tienen "
                    f"una cita entre {appt.scheduled_at} y {appt_end}."
                )