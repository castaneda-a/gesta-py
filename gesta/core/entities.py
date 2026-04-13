# =============================================================================
# entities.py
# =============================================================================
# Define las clases del dominio del negocio (Person, Role, Offering, Service,
# Product, Appointment, Transaction, Payment) y su mapeo a tablas SQL via
# SQLAlchemy ORM. Es la única fuente de verdad sobre qué datos existen y cómo
# se relacionan. No contiene lógica de negocio — solo estructura.
# =============================================================================


from decimal import Decimal
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Numeric,
    ForeignKey, Table, Enum
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PaymentMethod(PyEnum):
    CASH     = "cash"
    CARD     = "card"
    TRANSFER = "transfer"
    OTHER    = "other"


class AppointmentStatus(PyEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW   = "no_show"


class TransactionStatus(PyEnum):
    PENDING  = "pending"
    PAID     = "paid"
    PARTIAL  = "partial"
    REFUNDED = "refunded"


class OfferingType(PyEnum):
    SERVICE = "service"
    PRODUCT = "product"


# ---------------------------------------------------------------------------
# Tablas de asociación
# ---------------------------------------------------------------------------

person_roles = Table(
    "person_roles", Base.metadata,
    Column("person_id", String, ForeignKey("persons.id"), primary_key=True),
    Column("role_id",   String, ForeignKey("roles.id"),   primary_key=True),
)

appointment_clients = Table(
    "appointment_clients", Base.metadata,
    Column("appointment_id", String, ForeignKey("appointments.id"), primary_key=True),
    Column("person_id",      String, ForeignKey("persons.id"),      primary_key=True),
)

appointment_providers = Table(
    "appointment_providers", Base.metadata,
    Column("appointment_id", String, ForeignKey("appointments.id"), primary_key=True),
    Column("person_id",      String, ForeignKey("persons.id"),      primary_key=True),
)

transaction_clients = Table(
    "transaction_clients", Base.metadata,
    Column("transaction_id", String, ForeignKey("transactions.id"), primary_key=True),
    Column("person_id",      String, ForeignKey("persons.id"),      primary_key=True),
)

transaction_providers = Table(
    "transaction_providers", Base.metadata,
    Column("transaction_id", String, ForeignKey("transactions.id"), primary_key=True),
    Column("person_id",      String, ForeignKey("persons.id"),      primary_key=True),
)

payment_transactions = Table(
    "payment_transactions", Base.metadata,
    Column("payment_id",     String, ForeignKey("payments.id"),     primary_key=True),
    Column("transaction_id", String, ForeignKey("transactions.id"), primary_key=True),
)


# ---------------------------------------------------------------------------
# Person
# ---------------------------------------------------------------------------

class Person(Base):
    __tablename__ = "persons"

    id        = Column(String, primary_key=True)
    name      = Column(String(120), nullable=False)
    email     = Column(String(120), unique=True, nullable=True)
    phone     = Column(String(30),  nullable=True)
    notes     = Column(Text,        nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    roles                  = relationship("Role", secondary=person_roles, back_populates="persons")
    appointments_as_client = relationship("Appointment", secondary=appointment_clients, back_populates="clients")
    appointments_as_provider = relationship("Appointment", secondary=appointment_providers, back_populates="providers")
    transactions_as_client   = relationship("Transaction", secondary=transaction_clients, back_populates="clients")
    transactions_as_provider = relationship("Transaction", secondary=transaction_providers, back_populates="providers")

    def __repr__(self):
        return f"<Person id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------

class Role(Base):
    __tablename__ = "roles"

    id           = Column(String, primary_key=True)
    name         = Column(String(60), unique=True, nullable=False)
    description  = Column(Text, nullable=True)
    is_provider  = Column(Boolean, default=False, nullable=False)
    is_recipient = Column(Boolean, default=False, nullable=False)

    persons = relationship("Person", secondary=person_roles, back_populates="roles")

    def __repr__(self):
        return f"<Role name={self.name!r}>"


# ---------------------------------------------------------------------------
# Offering / Service / Product
# ---------------------------------------------------------------------------

class Offering(Base):
    __tablename__ = "offerings"

    id          = Column(String, primary_key=True)
    type        = Column(Enum(OfferingType), nullable=False)
    name        = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    price       = Column(Numeric(10, 2), nullable=False)    # precio por persona/unidad
    cost        = Column(Numeric(10, 2), nullable=True)   # costo para el negocio
    is_active   = Column(Boolean, default=True, nullable=False)
    created_at  = Column(DateTime, server_default=func.now(), nullable=False)

    # Solo para Service
    duration_minutes  = Column(String(10), nullable=True)
    requires_provider = Column(Boolean, default=True, nullable=True)

    # Solo para Product
    stock           = Column(Numeric(10, 2), nullable=True)
    track_inventory = Column(Boolean, default=True, nullable=True)

    @property
    def margin(self) -> Decimal | None:
        """
        Margen por unidad/persona.
        Retorna None si no se ha definido el costo.
        """
        if self.cost is None:
            return None
        return self.price - self.cost

    __mapper_args__ = {
        "polymorphic_on":       type,
        "polymorphic_identity": None,
    }

    def __repr__(self):
        return f"<Offering id={self.id} name={self.name!r} type={self.type}>"


class Service(Offering):
    __mapper_args__ = {"polymorphic_identity": OfferingType.SERVICE}


class Product(Offering):
    __mapper_args__ = {"polymorphic_identity": OfferingType.PRODUCT}


# ---------------------------------------------------------------------------
# Appointment
# ---------------------------------------------------------------------------

class Appointment(Base):
    __tablename__ = "appointments"

    id            = Column(String, primary_key=True)
    service_id    = Column(String, ForeignKey("offerings.id"), nullable=False)
    status        = Column(Enum(AppointmentStatus), default=AppointmentStatus.SCHEDULED, nullable=False)
    scheduled_at  = Column(DateTime, nullable=False)
    registered_at = Column(DateTime, server_default=func.now(), nullable=False)
    notes         = Column(Text, nullable=True)

    service     = relationship("Offering")
    clients     = relationship("Person", secondary=appointment_clients,   back_populates="appointments_as_client")
    providers   = relationship("Person", secondary=appointment_providers, back_populates="appointments_as_provider")
    transaction = relationship("Transaction", back_populates="appointment", uselist=False)

    def __repr__(self):
        return f"<Appointment id={self.id} scheduled_at={self.scheduled_at} status={self.status}>"


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class Transaction(Base):
    __tablename__ = "transactions"

    id             = Column(String, primary_key=True)
    appointment_id = Column(String, ForeignKey("appointments.id"), nullable=True)
    offering_id    = Column(String, ForeignKey("offerings.id"),    nullable=False)
    amount         = Column(Numeric(10, 2), nullable=False)   # precio total cobrado
    cost_amount    = Column(Numeric(10, 2), nullable=True)   # costo real en este momento
    status         = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)
    occurred_at    = Column(DateTime, nullable=False)
    created_at     = Column(DateTime, server_default=func.now(), nullable=False)
    notes          = Column(Text, nullable=True)

    appointment = relationship("Appointment", back_populates="transaction")
    offering    = relationship("Offering")
    clients     = relationship("Person", secondary=transaction_clients,   back_populates="transactions_as_client")
    providers   = relationship("Person", secondary=transaction_providers, back_populates="transactions_as_provider")
    payments    = relationship("Payment", secondary=payment_transactions, back_populates="transactions")

    @property
    def amount_paid(self) -> Decimal:
        """
        Suma la proporción de cada pago que corresponde a esta transacción.
        Si un pago cubre N transacciones, cada una recibe amount/N.
        """
        total = Decimal("0")
        for payment in self.payments:
            if not payment.is_refund:
                n = len(payment.transactions)
                total += payment.amount / n if n > 0 else Decimal("0")
        return total

    @property
    def balance(self) -> Decimal:
        """Monto pendiente de cobro."""
        return self.amount - self.amount_paid

    @property
    def profit(self) -> Decimal | None:
        """
        Ganancia o pérdida de la transacción.
        Retorna None si no se definió cost_amount.
        """
        if self.cost_amount is None:
            return None
        return self.amount - self.cost_amount

    @property
    def client_count(self) -> int:
        """Número de clientes en esta transacción."""
        return len(self.clients)

    @property
    def price_per_client(self) -> Decimal:
        """
        Precio promedio por cliente.
        Útil para verificar consistencia con Offering.price.
        """
        if self.client_count == 0:
            return Decimal("0")
        return self.amount / self.client_count

    def __repr__(self):
        return f"<Transaction id={self.id} amount={self.amount} status={self.status}>"


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

class Payment(Base):
    __tablename__ = "payments"

    id             = Column(String, primary_key=True)
    amount         = Column(Numeric(10, 2), nullable=False)
    method         = Column(Enum(PaymentMethod), nullable=False)
    is_refund      = Column(Boolean, default=False, nullable=False)
    paid_at        = Column(DateTime, nullable=False)
    created_at     = Column(DateTime, server_default=func.now(), nullable=False)
    notes          = Column(Text, nullable=True)

    transactions = relationship("Transaction", secondary=payment_transactions, back_populates="payments")


    def __repr__(self):
        kind = "Refund" if self.is_refund else "Payment"
        return f"<{kind} id={self.id} amount={self.amount} method={self.method}>"