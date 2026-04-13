# =============================================================================
# tests/test_entities.py
# =============================================================================
# Tests de las entidades del dominio: creación, relaciones, properties
# calculadas y validaciones a nivel de modelo.
# =============================================================================

from decimal import Decimal
from datetime import datetime, timedelta
import pytest

from gesta.core.entities import (
    Person, Role, Service, Product, Appointment, Transaction, Payment,
    OfferingType, AppointmentStatus, TransactionStatus, PaymentMethod,
    payment_transactions,
)


class TestPerson:

    def test_create_person(self, session, roles):
        person = Person(
            id    = "p1",
            name  = "Carlos Ruiz",
            email = "carlos@mail.com",
        )
        person.roles = [roles["client"]]
        session.add(person)
        session.flush()

        result = session.get(Person, "p1")
        assert result.name  == "Carlos Ruiz"
        assert result.email == "carlos@mail.com"

    def test_person_multiple_roles(self, session, roles):
        """Una persona puede tener más de un rol."""
        person = Person(id="p2", name="Dual Role")
        person.roles = [roles["client"], roles["therapist"]]
        session.add(person)
        session.flush()

        result = session.get(Person, "p2")
        role_names = {r.name for r in result.roles}
        assert "client"    in role_names
        assert "therapist" in role_names

    def test_person_defaults(self, session):
        person = Person(id="p3", name="Sin datos opcionales")
        session.add(person)
        session.flush()

        result = session.get(Person, "p3")
        assert result.email    is None
        assert result.phone    is None


class TestOffering:

    def test_create_service(self, session, service_masaje):
        result = session.get(Service, "svc_masaje")
        assert result.name  == "Masaje sueco"
        assert result.price == Decimal("600.00")
        assert result.cost  == Decimal("150.00")
        assert result.type  == OfferingType.SERVICE

    def test_service_margin(self, session, service_masaje):
        """margin = price - cost."""
        assert service_masaje.margin == Decimal("450.00")

    def test_service_margin_none_when_no_cost(self, session):
        """Si no hay costo definido, margin retorna None."""
        service = Service(
            id    = "svc_sin_costo",
            type  = OfferingType.SERVICE,
            name  = "Servicio sin costo",
            price = Decimal("500.00"),
            cost  = None,
        )
        session.add(service)
        session.flush()
        assert service.margin is None

    def test_create_product(self, session, product_aceite):
        result = session.get(Product, "prd_aceite")
        assert result.name  == "Aceite de lavanda"
        assert result.price == Decimal("180.00")
        assert result.cost  == Decimal("60.00")
        assert result.type  == OfferingType.PRODUCT
        assert result.stock == Decimal("50")


class TestTransaction:

    def test_amount_paid_single_payment(
        self, session, client_ana, therapist_marta, service_masaje
    ):
        """amount_paid suma correctamente un pago único."""
        tx = Transaction(
            id          = "tx1",
            offering_id = service_masaje.id,
            amount      = Decimal("600.00"),
            occurred_at = datetime.now(),
            status      = TransactionStatus.PENDING,
        )
        tx.clients   = [client_ana]
        tx.providers = [therapist_marta]
        session.add(tx)
        session.flush()

        payment = Payment(
            id        = "pay1",
            amount    = Decimal("600.00"),
            method    = PaymentMethod.CASH,
            is_refund = False,
            paid_at   = datetime.now(),
        )
        payment.transactions = [tx]
        session.add(payment)
        session.flush()

        session.refresh(tx)
        assert tx.amount_paid == Decimal("600.00")
        assert tx.balance     == Decimal("0.00")

    def test_amount_paid_shared_payment(
        self, session, client_ana, therapist_marta,
        client_luis, service_masaje, service_yoga
    ):
        """Un pago compartido entre dos transacciones divide el monto."""
        tx1 = Transaction(
            id="tx_shared1", offering_id=service_masaje.id,
            amount=Decimal("600.00"), occurred_at=datetime.now(),
            status=TransactionStatus.PENDING,
        )
        tx1.clients   = [client_ana]
        tx1.providers = [therapist_marta]

        tx2 = Transaction(
            id="tx_shared2", offering_id=service_yoga.id,
            amount=Decimal("120.00"), occurred_at=datetime.now(),
            status=TransactionStatus.PENDING,
        )
        tx2.clients   = [client_luis]
        tx2.providers = [therapist_marta]

        session.add_all([tx1, tx2])
        session.flush()

        payment = Payment(
            id="pay_shared", amount=Decimal("720.00"),
            method=PaymentMethod.CARD, is_refund=False,
            paid_at=datetime.now(),
        )
        payment.transactions = [tx1, tx2]
        session.add(payment)
        session.flush()

        session.refresh(tx1)
        session.refresh(tx2)

        # cada transacción recibe 720 / 2 = 360
        assert tx1.amount_paid == Decimal("360.00")
        assert tx2.amount_paid == Decimal("360.00")

    def test_profit(self, session, client_ana, therapist_marta, service_masaje):
        """profit = amount - cost_amount."""
        tx = Transaction(
            id="tx_profit", offering_id=service_masaje.id,
            amount=Decimal("600.00"), cost_amount=Decimal("150.00"),
            occurred_at=datetime.now(), status=TransactionStatus.PENDING,
        )
        tx.clients   = [client_ana]
        tx.providers = [therapist_marta]
        session.add(tx)
        session.flush()

        assert tx.profit == Decimal("450.00")

    def test_profit_none_when_no_cost(
        self, session, client_ana, therapist_marta, service_masaje
    ):
        """profit retorna None si no hay cost_amount."""
        tx = Transaction(
            id="tx_no_cost", offering_id=service_masaje.id,
            amount=Decimal("600.00"), cost_amount=None,
            occurred_at=datetime.now(), status=TransactionStatus.PENDING,
        )
        tx.clients   = [client_ana]
        tx.providers = [therapist_marta]
        session.add(tx)
        session.flush()

        assert tx.profit is None

    def test_price_per_client_single(
        self, session, client_ana, therapist_marta, service_masaje
    ):
        """price_per_client con un solo cliente es igual al amount."""
        tx = Transaction(
            id="tx_ppc1", offering_id=service_masaje.id,
            amount=Decimal("600.00"), occurred_at=datetime.now(),
            status=TransactionStatus.PENDING,
        )
        tx.clients   = [client_ana]
        tx.providers = [therapist_marta]
        session.add(tx)
        session.flush()

        assert tx.price_per_client == Decimal("600.00")

    def test_price_per_client_group(
        self, session, client_ana, client_luis,
        instructor_pedro, service_yoga
    ):
        """price_per_client divide el amount entre los clientes."""
        tx = Transaction(
            id="tx_ppc2", offering_id=service_yoga.id,
            amount=Decimal("240.00"), occurred_at=datetime.now(),
            status=TransactionStatus.PENDING,
        )
        tx.clients   = [client_ana, client_luis]
        tx.providers = [instructor_pedro]
        session.add(tx)
        session.flush()

        assert tx.price_per_client == Decimal("120.00")