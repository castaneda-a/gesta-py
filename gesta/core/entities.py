# =============================================================================
# entities.py
# =============================================================================
# Define las clases del dominio del negocio y su mapeo a tablas SQL via
# SQLAlchemy ORM.
# =============================================================================

import uuid
from decimal import Decimal
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Numeric, Integer,
    ForeignKey, Table, Enum
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func

def generate_uuid():
    return str(uuid.uuid4())

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


# ---------------------------------------------------------------------------
# Junction Tables
# ---------------------------------------------------------------------------

person_services = Table(
    "persons_services", Base.metadata,
    Column("id", String, primary_key=True, default=generate_uuid),
    Column("id_person", String, ForeignKey("persons.id"), nullable=False),
    Column("id_service", String, ForeignKey("services.id"), nullable=True),
)

person_appointments = Table(
    "persons_appointments", Base.metadata,
    Column("id", String, primary_key=True, default=generate_uuid),
    Column("id_person", String, ForeignKey("persons.id"), nullable=True),
    Column("id_appointment", String, ForeignKey("appointments.id"), nullable=True),
)

person_transactions = Table(
    "persons_transactions", Base.metadata,
    Column("id", String, primary_key=True, default=generate_uuid),
    Column("id_person", String, ForeignKey("persons.id"), nullable=False),
    Column("id_transaction", String, ForeignKey("transactions.id"), nullable=True),
)

person_roles = Table(
    "persons_roles", Base.metadata,
    Column("id", String, primary_key=True, default=generate_uuid),
    Column("id_person", String, ForeignKey("persons.id"), nullable=True),
    Column("id_role", String, ForeignKey("roles.id"), nullable=True),
)

transaction_payments = Table(
    "transactions_payments", Base.metadata,
    Column("id", String, primary_key=True, default=generate_uuid),
    Column("id_transaction", String, ForeignKey("transactions.id"), nullable=False),
    Column("id_payment", String, ForeignKey("payments.id"), nullable=True),
)


# ---------------------------------------------------------------------------
# Person
# ---------------------------------------------------------------------------

class Person(Base):
    __tablename__ = "persons"

    id           = Column(String, primary_key=True)
    name         = Column(String(120), nullable=False)
    email        = Column(String(120), nullable=True)
    phone        = Column(String(30),  nullable=True)
    is_provider  = Column(Boolean, nullable=False, default=False)
    is_recipient = Column(Boolean, nullable=False, default=True)
    notes        = Column(Text,        nullable=True)
    created_at   = Column(DateTime, server_default=func.now(), nullable=False)

    roles        = relationship("Role", secondary=person_roles, back_populates="persons")
    appointments = relationship("Appointment", secondary=person_appointments, back_populates="persons")
    transactions = relationship("Transaction", secondary=person_transactions, back_populates="persons")
    services     = relationship("Service", secondary=person_services, back_populates="persons")

    def __repr__(self):
        return f"<Person id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------

class Role(Base):
    __tablename__ = "roles"

    id          = Column(String, primary_key=True)
    name        = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)

    persons = relationship("Person", secondary=person_roles, back_populates="roles")

    def __repr__(self):
        return f"<Role name={self.name!r}>"


# ---------------------------------------------------------------------------
# Service & Product
# ---------------------------------------------------------------------------

class Service(Base):
    __tablename__ = "services"

    id             = Column(String, primary_key=True)
    name           = Column(String(120), nullable=False)
    description    = Column(Text, nullable=True)
    price          = Column(Numeric(10, 2), nullable=False)
    cost           = Column(Numeric(10, 2), nullable=True)
    duration_min   = Column(Integer, nullable=True)
    requires_space = Column(Boolean, nullable=False, default=False)
    is_active      = Column(Boolean, nullable=False, default=True)
    created_at     = Column(DateTime, server_default=func.now(), nullable=False)

    persons      = relationship("Person", secondary=person_services, back_populates="services")
    appointments = relationship("Appointment", back_populates="service")
    transactions = relationship("Transaction", back_populates="service")

    @property
    def margin(self) -> Decimal | None:
        if self.cost is None:
            return None
        return self.price - self.cost

    def __repr__(self):
        return f"<Service id={self.id} name={self.name!r}>"


class Product(Base):
    __tablename__ = "products"

    id          = Column(String, primary_key=True)
    name        = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    price       = Column(Numeric(10, 2), nullable=False)
    cost        = Column(Numeric(10, 2), nullable=True)
    stock       = Column(Integer, nullable=True)
    supplier    = Column(String(120), nullable=True)
    is_active   = Column(Boolean, nullable=False, default=True)
    created_at  = Column(DateTime, server_default=func.now(), nullable=False)

    transactions = relationship("Transaction", back_populates="product")

    @property
    def margin(self) -> Decimal | None:
        if self.cost is None:
            return None
        return self.price - self.cost

    def __repr__(self):
        return f"<Product id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Appointment
# ---------------------------------------------------------------------------

class Appointment(Base):
    __tablename__ = "appointments"

    id            = Column(String, primary_key=True)
    service_id    = Column(String, ForeignKey("services.id"), nullable=False)
    status        = Column(Enum(AppointmentStatus), nullable=False, default=AppointmentStatus.SCHEDULED)
    scheduled_at  = Column(DateTime, nullable=False)
    registered_at = Column(DateTime, server_default=func.now(), nullable=False)
    notes         = Column(Text, nullable=True)
    created_at    = Column(DateTime, server_default=func.now(), nullable=False)

    service      = relationship("Service", back_populates="appointments")
    persons      = relationship("Person", secondary=person_appointments, back_populates="appointments")
    transaction  = relationship("Transaction", back_populates="appointment", uselist=False)

    def __repr__(self):
        return f"<Appointment id={self.id} scheduled_at={self.scheduled_at} status={self.status}>"


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class Transaction(Base):
    __tablename__ = "transactions"

    id             = Column(String, primary_key=True)
    appointment_id = Column(String, ForeignKey("appointments.id"), nullable=True)
    service_id     = Column(String, ForeignKey("services.id"), nullable=True)
    product_id     = Column(String, ForeignKey("products.id"), nullable=True)
    amount         = Column(Numeric(10, 2), nullable=False)
    cost_amount    = Column(Numeric(10, 2), nullable=True)
    status         = Column(Enum(TransactionStatus), nullable=False, default=TransactionStatus.PENDING)
    occurred_at    = Column(DateTime, nullable=False)
    created_at     = Column(DateTime, server_default=func.now(), nullable=False)
    notes          = Column(Text, nullable=True)

    appointment = relationship("Appointment", back_populates="transaction")
    service     = relationship("Service", back_populates="transactions")
    product     = relationship("Product", back_populates="transactions")
    persons     = relationship("Person", secondary=person_transactions, back_populates="transactions")
    payments    = relationship("Payment", secondary=transaction_payments, back_populates="transactions")

    @property
    def amount_paid(self) -> Decimal:
        total = Decimal("0")
        for payment in self.payments:
            if not payment.is_refund:
                n = len(payment.transactions)
                total += payment.amount / n if n > 0 else Decimal("0")
        return total

    @property
    def balance(self) -> Decimal:
        return self.amount - self.amount_paid

    @property
    def profit(self) -> Decimal | None:
        if self.cost_amount is None:
            return None
        return self.amount - self.cost_amount

    @property
    def person_count(self) -> int:
        return len(self.persons)

    @property
    def price_per_person(self) -> Decimal:
        if self.person_count == 0:
            return Decimal("0")
        return self.amount / self.person_count

    def __repr__(self):
        return f"<Transaction id={self.id} amount={self.amount} status={self.status}>"


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

class Payment(Base):
    __tablename__ = "payments"

    id         = Column(String, primary_key=True)
    amount     = Column(Numeric(10, 2), nullable=False)
    method     = Column(Enum(PaymentMethod), nullable=False)
    is_refund  = Column(Boolean, nullable=False, default=False)
    paid_at    = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    notes      = Column(Text, nullable=True)

    transactions = relationship("Transaction", secondary=transaction_payments, back_populates="payments")

    def __repr__(self):
        kind = "Refund" if self.is_refund else "Payment"
        return f"<{kind} id={self.id} amount={self.amount} method={self.method}>"