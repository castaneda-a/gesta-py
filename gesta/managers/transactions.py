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
    Service,
    Product,
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
    validate_persons_are_recipients,
    validate_persons_are_providers,
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
        client_ids: list[str],
        occurred_at: datetime,
        service_id: str = None,
        product_id: str = None,
        provider_ids: list[str] = None,
        amount: Decimal = None,
        cost_amount: Decimal = None,
        notes: str = None,
    ) -> Transaction:
        """
        Registra una transacción directa sin cita previa.
        Debe especificar al menos `service_id` o `product_id`.
        """
        if not service_id and not product_id:
            raise ValidationError("Debe especificar service_id o product_id.")

        provider_ids = provider_ids or []
        validate_required_list(client_ids, "client_ids")

        clients   = self._get_persons_or_raise(client_ids)
        providers = self._get_persons_or_raise(provider_ids)

        validate_persons_are_recipients(clients)
        validate_persons_are_providers(providers)

        offering_price = Decimal("0")
        offering_cost = None
        service = None
        product = None

        if service_id:
            service = self.session.get(Service, service_id)
            if not service:
                raise NotFoundError("Service", service_id)
            if not service.is_active:
                raise ValidationError(f"Service {service_id!r} no está activo.")
            offering_price = service.price
            offering_cost = service.cost
            # Basic provider check for service
            if service.requires_space and not providers:
                # we just use a generic check if needed, or rely on validators
                pass
        elif product_id:
            product = self.session.get(Product, product_id)
            if not product:
                raise NotFoundError("Product", product_id)
            if not product.is_active:
                raise ValidationError(f"Product {product_id!r} no está activo.")
            offering_price = product.price
            offering_cost = product.cost

        n              = len(clients)
        final_amount   = amount      if amount      is not None else offering_price * n
        final_cost     = cost_amount if cost_amount is not None else (
            offering_cost * n if offering_cost is not None else None
        )

        validate_positive_amount(final_amount, "amount")

        tx = Transaction(
            id          = str(uuid.uuid4()),
            service_id  = service_id,
            product_id  = product_id,
            amount      = final_amount,
            cost_amount = final_cost,
            occurred_at = occurred_at,
            notes       = notes,
        )
        tx.service = service
        tx.product = product
        tx.persons = clients + providers
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
        self.session.refresh(appt)

        if appt.transaction is not None:
            raise BusinessRuleError(
                f"La cita {appointment_id!r} ya tiene una transacción "
                f"asociada (id={appt.transaction.id!r})."
            )

        if appt.status != AppointmentStatus.SCHEDULED:
            raise ValidationError(
                f"Solo se pueden registrar transacciones de citas SCHEDULED. "
                f"Estado actual: {appt.status.value!r}"
            )

        clients = [p for p in appt.persons if p.is_recipient]
        n            = len(clients) if len(clients) > 0 else 1
        final_amount = amount      if amount      is not None else appt.service.price * n
        final_cost   = cost_amount if cost_amount is not None else (
            appt.service.cost * n if appt.service.cost is not None else None
        )

        validate_positive_amount(final_amount, "amount")

        tx = Transaction(
            id             = str(uuid.uuid4()),
            appointment_id = appointment_id,
            service_id     = appt.service_id,
            amount         = final_amount,
            cost_amount    = final_cost,
            occurred_at    = occurred_at,
            notes          = notes,
        )
        tx.persons   = appt.persons
        tx.appointment = appt
        tx.service = appt.service
        appt.transaction = tx
        tx.status = TransactionStatus.PENDING
        appt.status = AppointmentStatus.COMPLETED

        self.session.add(tx)
        return tx

    # -----------------------------------------------------------------------
    # Consultas
    # -----------------------------------------------------------------------

    def get(self, transaction_id: str) -> Transaction:
        return self._get_transaction_or_raise(transaction_id)

    def list_by_client(self, client_id: str) -> list[Transaction]:
        return (
            self.session.query(Transaction)
            .options(
                selectinload(Transaction.service),
                selectinload(Transaction.product),
                selectinload(Transaction.persons),
            )
            .filter(Transaction.persons.any(Person.id == client_id))
            .order_by(Transaction.occurred_at.desc())
            .all()
        )

    def list_by_provider(self, provider_id: str) -> list[Transaction]:
        return (
            self.session.query(Transaction)
            .options(
                selectinload(Transaction.service),
                selectinload(Transaction.product),
                selectinload(Transaction.persons),
            )
            .filter(Transaction.persons.any(Person.id == provider_id))
            .order_by(Transaction.occurred_at.desc())
            .all()
        )

    def list_by_status(self, status: TransactionStatus) -> list[Transaction]:
        return (
            self.session.query(Transaction)
            .options(
                selectinload(Transaction.service),
                selectinload(Transaction.product),
                selectinload(Transaction.persons),
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
        return (
            self.session.query(Transaction)
            .options(
                selectinload(Transaction.service),
                selectinload(Transaction.product),
                selectinload(Transaction.persons),
            )
            .filter(
                Transaction.occurred_at >= start,
                Transaction.occurred_at <= end,
            )
            .order_by(Transaction.occurred_at.desc())
            .all()
        )

    def list_pending(self) -> list[Transaction]:
        return (
            self.session.query(Transaction)
            .options(
                selectinload(Transaction.service),
                selectinload(Transaction.product),
                selectinload(Transaction.persons),
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
        tx = self._get_transaction_or_raise(transaction_id)
        tx.status = status
        return tx


# =============================================================================
# PaymentManager
# =============================================================================

class PaymentManager:
    """
    Gestiona el registro de pagos y su asociación a transacciones.
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
        return self._get_payment_or_raise(payment_id)

    def list_by_transaction(self, transaction_id: str) -> list[Payment]:
        return (
            self.session.query(Payment)
            .options(
                selectinload(Payment.transactions).selectinload(Transaction.service),
                selectinload(Payment.transactions).selectinload(Transaction.product),
                selectinload(Payment.transactions).selectinload(Transaction.persons),
            )
            .filter(Payment.transactions.any(Transaction.id == transaction_id))
            .order_by(Payment.paid_at.desc())
            .all()
        )

    def list_by_method(self, method: PaymentMethod) -> list[Payment]:
        return (
            self.session.query(Payment)
            .options(
                selectinload(Payment.transactions).selectinload(Transaction.service),
                selectinload(Payment.transactions).selectinload(Transaction.product),
                selectinload(Payment.transactions).selectinload(Transaction.persons),
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
        return (
            self.session.query(Payment)
            .options(
                selectinload(Payment.transactions).selectinload(Transaction.service),
                selectinload(Payment.transactions).selectinload(Transaction.product),
                selectinload(Payment.transactions).selectinload(Transaction.persons),
            )
            .filter(
                Payment.paid_at >= start,
                Payment.paid_at <= end,
            )
            .order_by(Payment.paid_at.desc())
            .all()
        )