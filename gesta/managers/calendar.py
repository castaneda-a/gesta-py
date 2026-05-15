# =============================================================================
# calendar.py
# =============================================================================
# Gestor de citas. Centraliza toda la lógica de negocio relacionada con
# Appointment: crear, consultar, reagendar, cancelar y completar citas.
# Los managers nunca escriben SQL directo — usan la sesión de SQLAlchemy
# y delegan validaciones a validators.py.
# =============================================================================

import uuid
from datetime import datetime
from sqlalchemy.orm import Session, selectinload

from gesta.core.entities import (
    Appointment,
    AppointmentStatus,
    Offering,
    Person,
)
from gesta.core.exceptions import (
    NotFoundError,
    ValidationError,
    BusinessRuleError,
)
from gesta.core.validators import (
    validate_future_datetime,
    validate_required_list,
    validate_offering_is_active,
    validate_service_has_provider,
    validate_persons_are_recipients,
    validate_persons_are_providers,
    validate_no_schedule_conflict,
)


class AppointmentManager:
    """
    Gestiona el ciclo de vida completo de las citas.

    Uso:
        manager = AppointmentManager(session)
        appt = manager.book(
            service_id  = "abc123",
            client_ids  = ["cli1", "cli2"],
            provider_ids = ["pro1"],
            scheduled_at = datetime(2025, 6, 1, 10, 0),
        )
    """

    def __init__(self, session: Session):
        self.session = session

    # -----------------------------------------------------------------------
    # Helpers internos
    # -----------------------------------------------------------------------

    def _get_appointment_or_raise(self, appointment_id: str) -> Appointment:
        appt = self.session.get(Appointment, appointment_id)
        if not appt:
            raise NotFoundError("Appointment", appointment_id)
        return appt

    def _get_offering_or_raise(self, service_id: str) -> Offering:
        offering = self.session.get(Offering, service_id)
        if not offering:
            raise NotFoundError("Offering", service_id)
        return offering

    def _get_persons_or_raise(self, person_ids: list[str]) -> list[Person]:
        persons = []
        for pid in person_ids:
            person = self.session.get(Person, pid)
            if not person:
                raise NotFoundError("Person", pid)
            persons.append(person)
        return persons

    # -----------------------------------------------------------------------
    # Crear
    # -----------------------------------------------------------------------

    def book(
        self,
        service_id: str,
        client_ids: list[str],
        scheduled_at: datetime,
        provider_ids: list[str] = None,
        notes: str = None,
    ) -> Appointment:
        """
        Crea una nueva cita en estado SCHEDULED.

        Valida:
        - scheduled_at debe ser en el futuro
        - debe haber al menos un cliente
        - el servicio debe existir y estar activo
        - los clientes deben tener rol recipient
        - los proveedores deben tener rol provider
        - si el servicio requiere proveedor, debe haber al menos uno
        - ningún proveedor debe tener conflicto de horario
        """
        provider_ids = provider_ids or []

        # Validaciones de datos
        validate_future_datetime(scheduled_at, "scheduled_at")
        validate_required_list(client_ids, "client_ids")

        # Cargar entidades
        service   = self._get_offering_or_raise(service_id)
        clients   = self._get_persons_or_raise(client_ids)
        providers = self._get_persons_or_raise(provider_ids)

        # Validaciones de negocio
        validate_offering_is_active(service)
        validate_persons_are_recipients(clients)
        validate_persons_are_providers(providers)
        validate_service_has_provider(service, providers)

        duration = int(service.duration_minutes) if service.duration_minutes else 60
        validate_no_schedule_conflict(
            session      = self.session,
            provider_ids = provider_ids,
            scheduled_at = scheduled_at,
            duration_minutes = duration,
        )

        appt = Appointment(
            id           = str(uuid.uuid4()),
            service_id   = service_id,
            scheduled_at = scheduled_at,
            notes        = notes,
            status = AppointmentStatus.SCHEDULED,
        )
        appt.service = service
        appt.clients   = clients
        appt.providers = providers

        self.session.add(appt)
        return appt

    # -----------------------------------------------------------------------
    # Consultas
    # -----------------------------------------------------------------------

    def get(self, appointment_id: str) -> Appointment:
        """Retorna una cita por ID o lanza NotFoundError."""
        return self._get_appointment_or_raise(appointment_id)

    def list_by_date(self, date: datetime) -> list[Appointment]:
        """Retorna todas las citas del día de la fecha dada."""
        return (
            self.session.query(Appointment)
            .options(
                selectinload(Appointment.service),
                selectinload(Appointment.clients),
                selectinload(Appointment.providers),
            )
            .filter(
                Appointment.scheduled_at >= date.replace(hour=0, minute=0, second=0),
                Appointment.scheduled_at <= date.replace(hour=23, minute=59, second=59),
            )
            .order_by(Appointment.scheduled_at)
            .all()
        )

    def list_by_client(self, client_id: str) -> list[Appointment]:
        """Retorna todas las citas de un cliente."""
        return (
            self.session.query(Appointment)
            .options(
                selectinload(Appointment.service),
                selectinload(Appointment.clients),
                selectinload(Appointment.providers),
            )
            .filter(
                Appointment.clients.any(Person.id == client_id)
            )
            .order_by(Appointment.scheduled_at.desc())
            .all()
        )

    def list_by_provider(self, provider_id: str) -> list[Appointment]:
        """Retorna todas las citas de un proveedor."""
        return (
            self.session.query(Appointment)
            .options(
                selectinload(Appointment.service),
                selectinload(Appointment.clients),
                selectinload(Appointment.providers),
            )
            .filter(
                Appointment.providers.any(Person.id == provider_id)
            )
            .order_by(Appointment.scheduled_at.desc())
            .all()
        )

    def list_by_status(self, status: AppointmentStatus) -> list[Appointment]:
        """Retorna todas las citas con un estado dado."""
        return (
            self.session.query(Appointment)
            .options(
                selectinload(Appointment.service),
                selectinload(Appointment.clients),
                selectinload(Appointment.providers),
            )
            .filter(Appointment.status == status)
            .order_by(Appointment.scheduled_at)
            .all()
        )

    def list_upcoming(self) -> list[Appointment]:
        """Retorna todas las citas futuras en estado SCHEDULED."""
        return (
            self.session.query(Appointment)
            .options(
                selectinload(Appointment.service),
                selectinload(Appointment.clients),
                selectinload(Appointment.providers),
            )
            .filter(
                Appointment.status == AppointmentStatus.SCHEDULED,
                Appointment.scheduled_at > datetime.now(),
            )
            .order_by(Appointment.scheduled_at)
            .all()
        )

    # -----------------------------------------------------------------------
    # Modificar
    # -----------------------------------------------------------------------

    def reschedule(
        self,
        appointment_id: str,
        new_datetime: datetime,
    ) -> Appointment:
        """
        Cambia la fecha y hora de una cita existente.

        Solo se puede reagendar si la cita está en estado SCHEDULED.
        Valida conflictos de horario con los proveedores actuales.
        """
        appt = self._get_appointment_or_raise(appointment_id)

        if appt.status != AppointmentStatus.SCHEDULED:
            raise ValidationError(
                f"Solo se pueden reagendar citas en estado SCHEDULED. "
                f"Estado actual: {appt.status.value!r}"
            )

        validate_future_datetime(new_datetime, "new_datetime")

        duration = int(appt.service.duration_minutes) if appt.service.duration_minutes else 60
        validate_no_schedule_conflict(
            session          = self.session,
            provider_ids     = [p.id for p in appt.providers],
            scheduled_at     = new_datetime,
            duration_minutes = duration,
            exclude_appointment_id = appointment_id,
        )

        appt.scheduled_at = new_datetime
        return appt

    def cancel(self, appointment_id: str) -> Appointment:
        """
        Marca una cita como CANCELLED.

        Lanza un error si la cita ya tiene una transacción asociada,
        ya que el servicio fue impartido y no puede deshacerse.
        """
        appt = self._get_appointment_or_raise(appointment_id)

        if appt.status == AppointmentStatus.CANCELLED:
            raise ValidationError("La cita ya está cancelada.")

        if appt.transaction is not None:
            raise BusinessRuleError(
                f"No se puede cancelar la cita {appointment_id!r} porque "
                f"ya tiene una transacción asociada (id={appt.transaction.id!r}). "
                f"Gestiona la transacción directamente."
            )

        appt.status = AppointmentStatus.CANCELLED
        return appt

    def complete(self, appointment_id: str) -> Appointment:
        """
        Marca una cita como COMPLETED.
        Normalmente lo llama TransactionManager al registrar la transacción,
        pero puede usarse manualmente si el flujo lo requiere.
        """
        appt = self._get_appointment_or_raise(appointment_id)

        if appt.status != AppointmentStatus.SCHEDULED:
            raise ValidationError(
                f"Solo se pueden completar citas en estado SCHEDULED. "
                f"Estado actual: {appt.status.value!r}"
            )

        appt.status = AppointmentStatus.COMPLETED
        return appt

    def mark_no_show(self, appointment_id: str) -> Appointment:
        """
        Marca una cita como NO_SHOW — el cliente no se presentó.
        """
        appt = self._get_appointment_or_raise(appointment_id)

        if appt.status != AppointmentStatus.SCHEDULED:
            raise ValidationError(
                f"Solo se puede marcar no-show en citas SCHEDULED. "
                f"Estado actual: {appt.status.value!r}"
            )

        appt.status = AppointmentStatus.NO_SHOW
        return appt