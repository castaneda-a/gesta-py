# =============================================================================
# tests/test_transactions.py
# =============================================================================
# Tests de TransactionManager y PaymentManager: registro de transacciones,
# cálculo de montos, pagos simples y compartidos, reembolsos y estados.
# =============================================================================

from datetime import datetime, timedelta
from decimal import Decimal
import pytest

from gesta.managers.calendar import AppointmentManager
from gesta.managers.transactions import TransactionManager, PaymentManager
from gesta.core.entities import (
    AppointmentStatus, TransactionStatus, PaymentMethod,
)
from gesta.core.exceptions import (
    ValidationError,
    BusinessRuleError,
    NotFoundError,
)


@pytest.fixture
def appt_manager(session):
    return AppointmentManager(session)


@pytest.fixture
def tx_manager(session):
    return TransactionManager(session)


@pytest.fixture
def pay_manager(session):
    return PaymentManager(session)


@pytest.fixture
def booked_appointment(
    appt_manager, session,
    client_ana, therapist_marta, service_masaje, future_date
):
    """Cita agendada lista para convertirse en transacción."""
    appt = appt_manager.book(
        service_id   = service_masaje.id,
        client_ids   = [client_ana.id],
        provider_ids = [therapist_marta.id],
        scheduled_at = future_date,
    )
    session.flush()
    return appt


class TestTransactionManager:

    def test_register_direct(
        self, tx_manager, session,
        client_ana, therapist_marta, service_masaje
    ):
        """Registra una transacción directa sin cita previa."""
        tx = tx_manager.register(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            occurred_at  = datetime.now(),
        )
        session.flush()

        assert tx.id          is not None
        assert tx.amount      == Decimal("600.00")   # price × 1 cliente
        assert tx.cost_amount == Decimal("150.00")   # cost × 1 cliente
        assert tx.status      == TransactionStatus.PENDING

    def test_register_group_calculates_amount(
        self, tx_manager, session,
        client_ana, client_luis, instructor_pedro, service_yoga
    ):
        """El monto se calcula como price × número de clientes."""
        tx = tx_manager.register(
            service_id   = service_yoga.id,
            client_ids   = [client_ana.id, client_luis.id],
            provider_ids = [instructor_pedro.id],
            occurred_at  = datetime.now(),
        )
        session.flush()

        # yoga $120 × 2 clientes = $240
        assert tx.amount      == Decimal("240.00")
        # costo $300 × 2 = $600
        assert tx.cost_amount == Decimal("600.00")

    def test_register_custom_amount(
        self, tx_manager, session,
        client_ana, therapist_marta, service_masaje
    ):
        """Se puede especificar un monto custom (ej. descuento)."""
        tx = tx_manager.register(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            occurred_at  = datetime.now(),
            amount       = Decimal("500.00"),
        )
        session.flush()

        assert tx.amount == Decimal("500.00")

    def test_register_from_appointment(
        self, tx_manager, session,
        booked_appointment, service_masaje
    ):
        """Registra transacción desde una cita y la completa."""
        tx = tx_manager.register_from_appointment(
            appointment_id = booked_appointment.id,
            occurred_at    = datetime.now(),
        )
        session.flush()

        assert tx.appointment_id  == booked_appointment.id
        assert tx.amount          == Decimal("600.00")
        assert booked_appointment.status == AppointmentStatus.COMPLETED

    def test_register_from_appointment_twice_raises(
        self, tx_manager, session, booked_appointment
    ):
        """No se puede registrar dos transacciones para la misma cita."""
        tx_manager.register_from_appointment(
            appointment_id = booked_appointment.id,
            occurred_at    = datetime.now(),
        )
        session.flush()

        with pytest.raises(BusinessRuleError):
            tx_manager.register_from_appointment(
                appointment_id = booked_appointment.id,
                occurred_at    = datetime.now(),
            )

    def test_register_from_completed_appointment_raises(
        self, tx_manager, appt_manager, session, booked_appointment
    ):
        """No se puede registrar transacción de una cita ya completada."""
        appt_manager.complete(booked_appointment.id)
        session.flush()

        with pytest.raises(ValidationError):
            tx_manager.register_from_appointment(
                appointment_id = booked_appointment.id,
                occurred_at    = datetime.now(),
            )

    def test_profit_calculated(
        self, tx_manager, session,
        client_ana, therapist_marta, service_masaje
    ):
        """profit = amount - cost_amount."""
        tx = tx_manager.register(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            occurred_at  = datetime.now(),
        )
        session.flush()

        assert tx.profit == Decimal("450.00")


class TestPaymentManager:

    def test_register_full_payment(
        self, tx_manager, pay_manager, session,
        client_ana, therapist_marta, service_masaje
    ):
        """Un pago completo marca la transacción como PAID."""
        tx = tx_manager.register(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            occurred_at  = datetime.now(),
        )
        session.flush()

        pay_manager.register(
            transaction_ids = [tx.id],
            amount          = Decimal("600.00"),
            method          = PaymentMethod.CASH,
            paid_at         = datetime.now(),
        )
        session.flush()
        session.refresh(tx)

        assert tx.status      == TransactionStatus.PAID
        assert tx.balance     == Decimal("0.00")
        assert tx.amount_paid == Decimal("600.00")

    def test_register_partial_payment(
        self, tx_manager, pay_manager, session,
        client_ana, therapist_marta, service_masaje
    ):
        """Un pago parcial marca la transacción como PARTIAL."""
        tx = tx_manager.register(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            occurred_at  = datetime.now(),
        )
        session.flush()

        pay_manager.register(
            transaction_ids = [tx.id],
            amount          = Decimal("300.00"),
            method          = PaymentMethod.CARD,
            paid_at         = datetime.now(),
        )
        session.flush()
        session.refresh(tx)

        assert tx.status  == TransactionStatus.PARTIAL
        assert tx.balance == Decimal("300.00")

    def test_register_shared_payment(
        self, tx_manager, pay_manager, session,
        client_ana, client_luis,
        therapist_marta, instructor_pedro,
        service_masaje, service_yoga
    ):
        """Un pago cubre dos transacciones simultáneamente."""
        tx1 = tx_manager.register(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            occurred_at  = datetime.now(),
        )
        tx2 = tx_manager.register(
            service_id   = service_yoga.id,
            client_ids   = [client_luis.id],
            provider_ids = [instructor_pedro.id],
            occurred_at  = datetime.now(),
        )
        session.flush()

        pay_manager.register(
            transaction_ids = [tx1.id, tx2.id],
            amount          = Decimal("720.00"),
            method          = PaymentMethod.TRANSFER,
            paid_at         = datetime.now(),
        )
        session.flush()
        session.refresh(tx1)
        session.refresh(tx2)

        assert tx1.amount_paid == Decimal("360.00")
        assert tx2.amount_paid == Decimal("360.00")

    def test_payment_on_paid_transaction_raises(
        self, tx_manager, pay_manager, session,
        client_ana, therapist_marta, service_masaje
    ):
        """No se puede pagar una transacción ya saldada."""
        tx = tx_manager.register(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            occurred_at  = datetime.now(),
        )
        session.flush()

        pay_manager.register(
            transaction_ids = [tx.id],
            amount          = Decimal("600.00"),
            method          = PaymentMethod.CASH,
            paid_at         = datetime.now(),
        )
        session.flush()
        session.refresh(tx)

        with pytest.raises(ValidationError):
            pay_manager.register(
                transaction_ids = [tx.id],
                amount          = Decimal("100.00"),
                method          = PaymentMethod.CASH,
                paid_at         = datetime.now(),
            )

    def test_register_refund(
        self, tx_manager, pay_manager, session,
        client_ana, therapist_marta, service_masaje
    ):
        """Registra un reembolso y marca la transacción como REFUNDED."""
        tx = tx_manager.register(
            service_id   = service_masaje.id,
            client_ids   = [client_ana.id],
            provider_ids = [therapist_marta.id],
            occurred_at  = datetime.now(),
        )
        session.flush()

        pay_manager.register(
            transaction_ids = [tx.id],
            amount          = Decimal("600.00"),
            method          = PaymentMethod.CASH,
            paid_at         = datetime.now(),
        )
        session.flush()

        pay_manager.register_refund(
            transaction_ids = [tx.id],
            amount          = Decimal("600.00"),
            method          = PaymentMethod.CASH,
            paid_at         = datetime.now(),
            notes           = "Cliente insatisfecho",
        )
        session.flush()
        session.refresh(tx)

        assert tx.status == TransactionStatus.REFUNDED