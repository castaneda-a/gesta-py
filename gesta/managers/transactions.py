# =============================================================================
# transactions.py
# =============================================================================
# Gestores de transacciones y pagos. TransactionManager centraliza el registro
# de servicios impartidos y ventas. PaymentManager maneja el registro de pagos
# ligados a una o varias transacciones. Ambos managers trabajan juntos para
# mantener el estado financiero del negocio consistente.
# =============================================================================

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session, selectinload

from gesta.core.entities import (
    Transaction,
    TransactionStatus,
    Payment,
    PaymentMethod,
    Offering,
    Appointment,
    AppointmentStatus,
    Person,
)
from gesta.core.exceptions import (
    NotFoundError,
    ValidationError,
    BusinessRuleError,
    UnpaidTransactionError,
)
from gesta.core.validators import (
    validate_positive_amount,
    validate_required_list,
    validate_offering_is_active,
    validate_service_has_provider,
    validate_persons_are_recipients,
    validate_persons_are_providers,
    validate_payment_does_not_exceed_balance,
)


# =============================================================================
# TransactionManager
# =============================================================================

class TransactionManager:
    """
    Gestiona el ciclo de vida de las transacciones.

    Una transacción representa un servicio impartido o una venta realizada.
    Puede originarse desde una cita existente o registrarse directamente
    sin cita previa (venta espontánea).

    Uso desde cita:
        manager = TransactionManager(session)
        tx = manager.register_from_appointment(
            appointment_id = "abc123",
            occurred_at    = datetime.now(),
        )

    Uso directo:
        tx = manager.register(
            offering_id  = "srv456",
            client_ids   = ["cli1"],
            provider_ids = ["pro1"],
            amount       = Decimal("600.00"),
            occurred_at  = datetime.now(),
        )
    """

    def __init__(self, session: Session):
        self.session = session

    # -----------------------------------------------------------------------
    # Helpers internos
    # -----------------------------------------------------------------------

    def _get_transaction_or_raise(self, transaction_id: str) -> Transaction:
        tx = self.session.get(Transaction, transaction_id)
        if not tx:
            raise NotFoundError("Transaction", transaction_id)
        return tx

    def _get_offering_or_raise(self, offering_id: str) -> Offering:
        offering = self.session.get(Offering, offering_id)
        if not offering:
            raise NotFoundError("Offering", offering_id)
        return offering

    def _get_persons_or_raise(self, person_ids: list[str]) -> list[Person]:
        persons = []
        for pid in person_ids:
            person = self.session.get(Person, pid)
            if not person:
                raise NotFoundError("Person", pid)
            persons.append(person)
        return persons

    def _get_appointment_or_raise(self, appointment_id: str) -> Appointment:
        appt = self.session.get(Appointment, appointment_id)
        if not appt:
            raise NotFoundError("Appointment", appointment_id)
        return appt

    # -----------------------------------------------------------------------
    # Crear
    # -----------------------------------------------------------------------

    def register(
        self,
        offering_id: str,
        client_ids: list[str],
        occurred_at: datetime,
        provider_ids: list[str] = None,
        amount: Decimal = None,       # si None, se calcula como price × clientes
        cost_amount: Decimal = None,  # si None, se toma de offering.cost × clientes
        notes: str = None,
    ) -> Transaction:
        """
        Registra una transacción directa sin cita previa.

        Si no se especifica amount, se calcula automáticamente
        como offering.price × número de clientes.
        Si no se especifica cost_amount, se calcula como
        offering.cost × número de clientes (si el offering tiene costo definido).
        """
        provider_ids = provider_ids or []

        validate_required_list(client_ids, "client_ids")

        offering  = self._get_offering_or_raise(offering_id)
        clients   = self._get_persons_or_raise(client_ids)
        providers = self._get_persons_or_raise(provider_ids)

        validate_offering_is_active(offering)
        validate_persons_are_recipients(clients)
        validate_persons_are_providers(providers)
        validate_service_has_provider(offering, providers)

        # Calcular montos si no se especifican
        n              = len(clients)
        final_amount   = amount      if amount      is not None else offering.price * n
        final_cost     = cost_amount if cost_amount is not None else (
            offering.cost * n if offering.cost is not None else None
        )

        validate_positive_amount(final_amount, "amount")

        tx = Transaction(
            id          = str(uuid.uuid4()),
            offering_id = offering_id,
            amount      = final_amount,
            cost_amount = final_cost,
            occurred_at = occurred_at,
            notes       = notes,
        )
        tx.offering = offering
        tx.clients   = clients
        tx.providers = providers
        tx.status = TransactionStatus.PENDING

        self.session.add(tx)
        return tx


    def register_from_appointment(
        self,
        appointment_id: str,
        occurred_at: datetime,
        amount: Decimal = None,
        cost_amount: Decimal = None,
        notes: str = None,
    ) -> Transaction:
        appt = self._get_appointment_or_raise(appointment_id)

        # Recargar para asegurar que las relaciones estén actualizadas
        self.session.refresh(appt)

        # Primero: ¿ya tiene transacción? (error más específico)
        if appt.transaction is not None:
            raise BusinessRuleError(
                f"La cita {appointment_id!r} ya tiene una transacción "
                f"asociada (id={appt.transaction.id!r})."
            )

        # Segundo: ¿está en estado correcto?
        if appt.status != AppointmentStatus.SCHEDULED:
            raise ValidationError(
                f"Solo se pueden registrar transacciones de citas SCHEDULED. "
                f"Estado actual: {appt.status.value!r}"
            )

        n            = len(appt.clients)
        final_amount = amount      if amount      is not None else appt.service.price * n
        final_cost   = cost_amount if cost_amount is not None else (
            appt.service.cost * n if appt.service.cost is not None else None
        )

        validate_positive_amount(final_amount, "amount")

        tx = Transaction(
            id             = str(uuid.uuid4()),
            appointment_id = appointment_id,
            offering_id    = appt.service_id,
            amount         = final_amount,
            cost_amount    = final_cost,
            occurred_at    = occurred_at,
            notes          = notes,
        )
        tx.clients   = appt.clients
        tx.providers = appt.providers
        tx.appointment = appt
        tx.offering = appt.service
        appt.transaction = tx
        tx.status = TransactionStatus.PENDING
        appt.status = AppointmentStatus.COMPLETED

        self.session.add(tx)
        return tx

    # -----------------------------------------------------------------------
    # Consultas
    # -----------------------------------------------------------------------

    def get(self, transaction_id: str) -> Transaction:
        """Retorna una transacción por ID o lanza NotFoundError."""
        return self._get_transaction_or_raise(transaction_id)

    def list_by_client(self, client_id: str) -> list[Transaction]:
        """Retorna todas las transacciones de un cliente."""
        return (
            self.session.query(Transaction)
            .options(
                selectinload(Transaction.offering),
                selectinload(Transaction.clients),
                selectinload(Transaction.providers),
            )
            .filter(Transaction.clients.any(Person.id == client_id))
            .order_by(Transaction.occurred_at.desc())
            .all()
        )

    def list_by_provider(self, provider_id: str) -> list[Transaction]:
        """Retorna todas las transacciones de un proveedor."""
        return (
            self.session.query(Transaction)
            .options(
                selectinload(Transaction.offering),
                selectinload(Transaction.clients),
                selectinload(Transaction.providers),
            )
            .filter(Transaction.providers.any(Person.id == provider_id))
            .order_by(Transaction.occurred_at.desc())
            .all()
        )

    def list_by_status(self, status: TransactionStatus) -> list[Transaction]:
        """Retorna todas las transacciones con un estado dado."""
        return (
            self.session.query(Transaction)
            .options(
                selectinload(Transaction.offering),
                selectinload(Transaction.clients),
                selectinload(Transaction.providers),
            )
            .filter(Transaction.status == status)
            .order_by(Transaction.occurred_at.desc())
            .all()
        )

    def list_by_date_range(
        self,
        start: datetime,
        end: datetime,
    ) -> list[Transaction]:
        """Retorna todas las transacciones dentro de un rango de fechas."""
        return (
            self.session.query(Transaction)
            .options(
                selectinload(Transaction.offering),
                selectinload(Transaction.clients),
                selectinload(Transaction.providers),
            )
            .filter(
                Transaction.occurred_at >= start,
                Transaction.occurred_at <= end,
            )
            .order_by(Transaction.occurred_at.desc())
            .all()
        )

    def list_pending(self) -> list[Transaction]:
        """Retorna todas las transacciones con balance pendiente."""
        return (
            self.session.query(Transaction)
            .options(
                selectinload(Transaction.offering),
                selectinload(Transaction.clients),
                selectinload(Transaction.providers),
            )
            .filter(Transaction.status == TransactionStatus.PENDING)
            .order_by(Transaction.occurred_at)
            .all()
        )

    # -----------------------------------------------------------------------
    # Modificar
    # -----------------------------------------------------------------------

    def update_status(
        self,
        transaction_id: str,
        status: TransactionStatus,
    ) -> Transaction:
        """
        Actualiza el estado de una transacción manualmente.
        En el flujo normal el estado se actualiza automáticamente
        al registrar pagos via PaymentManager.
        """
        tx = self._get_transaction_or_raise(transaction_id)
        tx.status = status
        return tx


# =============================================================================
# PaymentManager
# =============================================================================

class PaymentManager:
    """
    Gestiona el registro de pagos y su asociación a transacciones.

    Un pago puede cubrir una o varias transacciones simultáneamente.
    El estado de cada transacción se actualiza automáticamente
    al registrar o revertir un pago.

    Uso — pago simple:
        manager = PaymentManager(session)
        payment = manager.register(
            transaction_ids = ["tx1"],
            amount          = Decimal("600.00"),
            method          = PaymentMethod.CASH,
            paid_at         = datetime.now(),
        )

    Uso — pago que cubre varias transacciones:
        payment = manager.register(
            transaction_ids = ["tx1", "tx2"],
            amount          = Decimal("1100.00"),
            method          = PaymentMethod.CARD,
            paid_at         = datetime.now(),
        )
    """

    def __init__(self, session: Session):
        self.session = session

    # -----------------------------------------------------------------------
    # Helpers internos
    # -----------------------------------------------------------------------

    def _get_payment_or_raise(self, payment_id: str) -> Payment:
        payment = self.session.get(Payment, payment_id)
        if not payment:
            raise NotFoundError("Payment", payment_id)
        return payment

    def _get_transaction_or_raise(self, transaction_id: str) -> Transaction:
        tx = self.session.get(Transaction, transaction_id)
        if not tx:
            raise NotFoundError("Transaction", transaction_id)
        return tx

    def _get_transactions_or_raise(
        self, transaction_ids: list[str]
    ) -> list[Transaction]:
        transactions = []
        for tid in transaction_ids:
            transactions.append(self._get_transaction_or_raise(tid))
        return transactions

    def _update_transaction_status(self, tx: Transaction) -> None:
        """
        Recalcula y actualiza el estado de una transacción
        basándose en su balance actual.
        """
        balance = tx.balance

        if balance <= Decimal("0"):
            tx.status = TransactionStatus.PAID
        elif balance < tx.amount:
            tx.status = TransactionStatus.PARTIAL
        else:
            tx.status = TransactionStatus.PENDING

    # -----------------------------------------------------------------------
    # Registrar
    # -----------------------------------------------------------------------

    def register(
        self,
        transaction_ids: list[str],
        amount: Decimal,
        method: PaymentMethod,
        paid_at: datetime,
        notes: str = None,
    ) -> Payment:
        """
        Registra un pago y lo liga a una o varias transacciones.
        Actualiza el estado de cada transacción automáticamente.

        Valida:
        - debe haber al menos una transacción
        - el monto debe ser positivo
        - ninguna transacción debe estar ya en estado PAID o REFUNDED
        """
        validate_required_list(transaction_ids, "transaction_ids")
        validate_positive_amount(amount, "amount")

        transactions = self._get_transactions_or_raise(transaction_ids)

        for tx in transactions:
            if tx.status == TransactionStatus.PAID:
                raise ValidationError(
                    f"La transacción {tx.id!r} ya está completamente pagada."
                )
            if tx.status == TransactionStatus.REFUNDED:
                raise ValidationError(
                    f"La transacción {tx.id!r} está reembolsada y no acepta pagos."
                )

        payment = Payment(
            id        = str(uuid.uuid4()),
            amount    = amount,
            method    = method,
            is_refund = False,
            paid_at   = paid_at,
            notes     = notes,
        )
        payment.is_refund = False
        payment.transactions = transactions

        self.session.add(payment)

        for tx in transactions:
            self._update_transaction_status(tx)

        return payment

    def register_refund(
        self,
        transaction_ids: list[str],
        amount: Decimal,
        method: PaymentMethod,
        paid_at: datetime,
        notes: str = None,
    ) -> Payment:
        """
        Registra un reembolso contra una o varias transacciones.
        Actualiza el estado de cada transacción automáticamente.

        Valida:
        - el monto debe ser positivo
        - cada transacción debe tener suficiente monto pagado para reembolsar
        """
        validate_required_list(transaction_ids, "transaction_ids")
        validate_positive_amount(amount, "amount")

        transactions = self._get_transactions_or_raise(transaction_ids)

        refund = Payment(
            id        = str(uuid.uuid4()),
            amount    = amount,
            method    = method,
            is_refund = True,
            paid_at   = paid_at,
            notes     = notes,
        )
        refund.transactions = transactions

        self.session.add(refund)

        for tx in transactions:
            if tx.amount_paid < Decimal("0"):
                raise ValidationError(
                    f"El reembolso excede el monto pagado "
                    f"en la transacción {tx.id!r}."
                )
            tx.status = TransactionStatus.REFUNDED

        return refund

    # -----------------------------------------------------------------------
    # Consultas
    # -----------------------------------------------------------------------

    def get(self, payment_id: str) -> Payment:
        """Retorna un pago por ID o lanza NotFoundError."""
        return self._get_payment_or_raise(payment_id)

    def list_by_transaction(self, transaction_id: str) -> list[Payment]:
        """Retorna todos los pagos asociados a una transacción."""
        tx = self._get_transaction_or_raise(transaction_id)
        return (
            self.session.query(Payment)
            .options(
                selectinload(Payment.transactions).selectinload(Transaction.offering),
                selectinload(Payment.transactions).selectinload(Transaction.clients),
                selectinload(Payment.transactions).selectinload(Transaction.providers),
            )
            .filter(Payment.transactions.any(Transaction.id == transaction_id))
            .order_by(Payment.paid_at.desc())
            .all()
        )

    def list_by_method(self, method: PaymentMethod) -> list[Payment]:
        """Retorna todos los pagos por método de pago."""
        return (
            self.session.query(Payment)
            .options(
                selectinload(Payment.transactions).selectinload(Transaction.offering),
                selectinload(Payment.transactions).selectinload(Transaction.clients),
                selectinload(Payment.transactions).selectinload(Transaction.providers),
            )
            .filter(Payment.method == method)
            .order_by(Payment.paid_at.desc())
            .all()
        )

    def list_by_date_range(
        self,
        start: datetime,
        end: datetime,
    ) -> list[Payment]:
        """Retorna todos los pagos dentro de un rango de fechas."""
        return (
            self.session.query(Payment)
            .options(
                selectinload(Payment.transactions).selectinload(Transaction.offering),
                selectinload(Payment.transactions).selectinload(Transaction.clients),
                selectinload(Payment.transactions).selectinload(Transaction.providers),
            )
            .filter(
                Payment.paid_at >= start,
                Payment.paid_at <= end,
            )
            .order_by(Payment.paid_at.desc())
            .all()
        )