# =============================================================================
# tests/test_calendar.py
# =============================================================================
# Tests del AppointmentManager: crear, consultar, reagendar, cancelar
# y completar citas. Incluye tests de validaciones y reglas de negocio.
# =============================================================================

from datetime import datetime, timedelta
from decimal import Decimal
import pytest

from gesta.managers.calendar import AppointmentManager
from gesta.core.entities import AppointmentStatus, Transaction, TransactionStatus
from gesta.core.exceptions import (
    ValidationError,
    NotFoundError,
    BusinessRuleError,
    InactiveOfferingError,
    NoProviderError,
    InvalidRoleError,
    AppointmentConflictError,
)


@pytest.fixture
def manager(session):
    return AppointmentManager(session)


class TestBook:

    def test_book_simple(
        self, manager, session,
        client_ana, therapist_marta, service_masaje, future_date
    ):
        """Crea una cita válida con un cliente y un proveedor."""
        appt = manager.book(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            scheduled_at = future_date,
        )
        session.flush()

        assert appt.id           is not None
        assert appt.status       == AppointmentStatus.SCHEDULED
        assert len([p for p in appt.persons if p.is_recipient]) == 1
        assert len([p for p in appt.persons if p.is_provider])  == 1

    def test_book_group(
        self, manager, session,
        client_ana, client_luis, instructor_pedro, service_yoga, future_date
    ):
        """Crea una cita grupal con múltiples clientes."""
        appt = manager.book(
            service_id   = service_yoga.id,
            client_ids   = [client_ana.id, client_luis.id],
            provider_ids = [instructor_pedro.id],
            scheduled_at = future_date,
        )
        session.flush()

        assert len([p for p in appt.persons if p.is_recipient]) == 2

    def test_book_past_date_raises(
        self, manager, client_ana, therapist_marta, service_masaje, past_date
    ):
        """No se puede agendar en el pasado."""
        with pytest.raises(ValidationError):
            manager.book(
                service_id   = service_masaje.id,
                client_ids   = [client_ana.id],
                provider_ids = [therapist_marta.id],
                scheduled_at = past_date,
            )

    def test_book_no_clients_raises(
        self, manager, therapist_marta, service_masaje, future_date
    ):
        """No se puede agendar sin clientes."""
        with pytest.raises(ValidationError):
            manager.book(
                service_id   = service_masaje.id,
                client_ids   = [],
                provider_ids = [therapist_marta.id],
                scheduled_at = future_date,
            )

    def test_book_inactive_service_raises(
        self, manager, session, client_ana, therapist_marta, future_date
    ):
        """No se puede agendar un servicio inactivo."""
        from gesta.core.entities import Service
        inactive = Service(
            id="svc_inactive", name="Inactivo", price=Decimal("100.00"),
            duration_min=60, requires_space=True,
            is_active=False,
        )
        session.add(inactive)
        session.flush()

        with pytest.raises(InactiveOfferingError):
            manager.book(
                service_id   = inactive.id,
                client_ids   = [client_ana.id],
                provider_ids = [therapist_marta.id],
                scheduled_at = future_date,
            )

    def test_book_wrong_role_raises(
        self, manager, client_ana, therapist_marta, service_masaje, future_date
    ):
        """No se puede usar un cliente como proveedor si no tiene el rol is_provider."""
        with pytest.raises(InvalidRoleError):
            manager.book(
                service_id   = service_masaje.id,
                client_ids   = [client_ana.id],
                provider_ids = [client_ana.id],
                scheduled_at = future_date,
            )

    def test_book_conflict_raises(
        self, manager, session,
        client_ana, therapist_marta, service_masaje, future_date
    ):
        """No se puede agendar si el proveedor ya tiene cita en ese horario."""
        manager.book(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            scheduled_at = future_date,
        )
        session.flush()

        with pytest.raises(AppointmentConflictError):
            manager.book(
                service_id   = service_masaje.id,
                client_ids   = [client_ana.id],
                provider_ids = [therapist_marta.id],
                scheduled_at = future_date + timedelta(minutes=30),
            )


class TestReschedule:

    def test_reschedule(
        self, manager, session,
        client_ana, therapist_marta, service_masaje, future_date
    ):
        """Reagenda una cita a una nueva fecha válida."""
        appt = manager.book(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            scheduled_at = future_date,
        )
        session.flush()

        new_date = future_date + timedelta(days=3)
        manager.reschedule(appt.id, new_date)

        assert appt.scheduled_at == new_date

    def test_reschedule_past_raises(
        self, manager, session,
        client_ana, therapist_marta, service_masaje, future_date, past_date
    ):
        """No se puede reagendar a una fecha pasada."""
        appt = manager.book(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            scheduled_at = future_date,
        )
        session.flush()

        with pytest.raises(ValidationError):
            manager.reschedule(appt.id, past_date)

    def test_reschedule_completed_raises(
        self, manager, session,
        client_ana, therapist_marta, service_masaje, future_date
    ):
        """No se puede reagendar una cita completada."""
        appt = manager.book(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            scheduled_at = future_date,
        )
        session.flush()
        manager.complete(appt.id)

        with pytest.raises(ValidationError):
            manager.reschedule(appt.id, future_date + timedelta(days=1))


class TestCancel:

    def test_cancel(
        self, manager, session,
        client_ana, therapist_marta, service_masaje, future_date
    ):
        """Cancela una cita sin transacción."""
        appt = manager.book(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            scheduled_at = future_date,
        )
        session.flush()
        manager.cancel(appt.id)

        assert appt.status == AppointmentStatus.CANCELLED

    def test_cancel_with_transaction_raises(
        self, manager, session,
        client_ana, therapist_marta, service_masaje, future_date
    ):
        """No se puede cancelar una cita con transacción asociada."""
        appt = manager.book(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            scheduled_at = future_date,
        )
        session.flush()

        tx = Transaction(
            id="tx_cancel_test", service_id=service_masaje.id,
            appointment_id=appt.id, amount=Decimal("600.00"),
            occurred_at=datetime.now(), status=TransactionStatus.PENDING,
        )
        tx.persons = [client_ana, therapist_marta]
        session.add(tx)
        session.flush()

        with pytest.raises(BusinessRuleError):
            manager.cancel(appt.id)

    def test_cancel_already_cancelled_raises(
        self, manager, session,
        client_ana, therapist_marta, service_masaje, future_date
    ):
        """No se puede cancelar una cita ya cancelada."""
        appt = manager.book(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            scheduled_at = future_date,
        )
        session.flush()
        manager.cancel(appt.id)

        with pytest.raises(ValidationError):
            manager.cancel(appt.id)


class TestQueries:

    def test_list_upcoming(
        self, manager, session,
        client_ana, therapist_marta, service_masaje, future_date
    ):
        """list_upcoming retorna citas futuras en estado SCHEDULED."""
        manager.book(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            scheduled_at = future_date,
        )
        session.flush()

        upcoming = manager.list_upcoming()
        assert len(upcoming) >= 1

    def test_get_not_found_raises(self, manager):
        """get lanza NotFoundError si la cita no existe."""
        with pytest.raises(NotFoundError):
            manager.get("id_inexistente")