# =============================================================================
# reports.py
# =============================================================================
# Gestor de reportes y resúmenes financieros. Provee consultas agregadas
# sobre transacciones y pagos para obtener métricas del negocio: ingresos,
# métodos de pago, servicios populares, clientes frecuentes, etc.
# No escribe datos — solo lee y agrega.
# =============================================================================

from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func

from gesta.core.entities import (
    Transaction,
    TransactionStatus,
    Payment,
    PaymentMethod,
    Appointment,
    AppointmentStatus,
    Service,
    Product,
    Person,
)


# ---------------------------------------------------------------------------
# Dataclasses de resultados
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field


@dataclass
class RevenueSummary:
    """Resumen financiero de un período."""
    period_start:      datetime
    period_end:        datetime
    total_revenue:     Decimal   # suma de transaction.amount
    total_cost:        Decimal   # suma de transaction.cost_amount
    total_profit:      Decimal   # total_revenue - total_cost
    total_collected:   Decimal   # pagos realmente recibidos
    total_pending:     Decimal   # balance sin cobrar
    by_method:         dict[str, Decimal] = field(default_factory=dict)
    transaction_count: int = 0
    payment_count:     int = 0

    @property
    def profit_margin(self) -> float | None:
        """Margen de ganancia como porcentaje."""
        if self.total_revenue == 0:
            return None
        return round(float(self.total_profit / self.total_revenue * 100), 2)


@dataclass
class OfferingStats:
    """Estadísticas de un servicio o producto."""
    offering_id:    str
    offering_name:  str
    count:          int
    total_revenue:  Decimal
    total_cost:     Decimal
    total_profit:   Decimal

    @property
    def profit_margin(self) -> float | None:
        if self.total_revenue == 0:
            return None
        return round(float(self.total_profit / self.total_revenue * 100), 2)


@dataclass
class PersonStats:
    """Estadísticas de un cliente o proveedor."""
    person_id:         str
    person_name:       str
    transaction_count: int
    total_spent:       Decimal   # para clientes: lo que pagaron
    total_generated:   Decimal   # para proveedores: ingresos que generaron


@dataclass
class AppointmentSummary:
    """Resumen del estado de citas en un período."""
    period_start: datetime
    period_end:   datetime
    scheduled:    int
    completed:    int
    cancelled:    int
    no_show:      int

    @property
    def total(self) -> int:
        return self.scheduled + self.completed + self.cancelled + self.no_show

    @property
    def completion_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.completed / self.total * 100, 2)


# =============================================================================
# ReportManager
# =============================================================================

class ReportManager:
    """
    Genera reportes y métricas del negocio a partir de los datos existentes.
    """

    def __init__(self, session: Session):
        self.session = session

    # -----------------------------------------------------------------------
    # Helpers internos
    # -----------------------------------------------------------------------

    def _date_range_for_month(self, year: int, month: int):
        start = datetime(year, month, 1, 0, 0, 0)
        if month == 12:
            end = datetime(year + 1, 1, 1, 0, 0, 0) - timedelta(seconds=1)
        else:
            end = datetime(year, month + 1, 1, 0, 0, 0) - timedelta(seconds=1)
        return start, end

    def _transactions_in_range(
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
            .all()
        )

    def _payments_in_range(
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
                Payment.is_refund == False,
                Payment.paid_at >= start,
                Payment.paid_at <= end,
            )
            .all()
        )

    # -----------------------------------------------------------------------
    # Ingresos
    # -----------------------------------------------------------------------

    def revenue_summary(
        self,
        start: datetime,
        end: datetime,
    ) -> RevenueSummary:
        transactions = self._transactions_in_range(start, end)
        payments     = self._payments_in_range(start, end)

        total_revenue   = sum(tx.amount for tx in transactions)
        total_cost      = sum(
            tx.cost_amount for tx in transactions if tx.cost_amount is not None
        )
        total_profit    = total_revenue - total_cost
        total_collected = sum(p.amount for p in payments)
        total_pending   = sum(tx.balance for tx in transactions)

        by_method: dict[str, Decimal] = defaultdict(Decimal)
        for p in payments:
            by_method[p.method.value] += p.amount

        return RevenueSummary(
            period_start      = start,
            period_end        = end,
            total_revenue     = Decimal(str(total_revenue)),
            total_cost        = Decimal(str(total_cost)),
            total_profit      = Decimal(str(total_profit)),
            total_collected   = Decimal(str(total_collected)),
            total_pending     = Decimal(str(total_pending)),
            by_method         = dict(by_method),
            transaction_count = len(transactions),
            payment_count     = len(payments),
        )

    def monthly_summary(self, year: int, month: int) -> RevenueSummary:
        start, end = self._date_range_for_month(year, month)
        return self.revenue_summary(start, end)

    def daily_revenue(
        self,
        start: datetime,
        end: datetime,
    ) -> dict[str, Decimal]:
        payments = self._payments_in_range(start, end)
        by_day: dict[str, Decimal] = defaultdict(Decimal)
        for p in payments:
            day = p.paid_at.strftime("%Y-%m-%d")
            by_day[day] += p.amount
        return dict(sorted(by_day.items()))

    # -----------------------------------------------------------------------
    # Offerings
    # -----------------------------------------------------------------------

    def most_popular_offerings(
        self,
        start: datetime,
        end: datetime,
        top: int = 5,
    ) -> list[OfferingStats]:
        transactions = self._transactions_in_range(start, end)

        counts:   dict[str, int]     = defaultdict(int)
        revenues: dict[str, Decimal] = defaultdict(Decimal)
        costs:    dict[str, Decimal] = defaultdict(Decimal)
        names:    dict[str, str]     = {}

        for tx in transactions:
            oid = tx.service_id or tx.product_id
            if not oid:
                continue
            
            counts[oid]   += 1
            revenues[oid] += tx.amount
            costs[oid]    += tx.cost_amount if tx.cost_amount is not None else Decimal("0")
            
            if oid not in names:
                if tx.service:
                    names[oid] = tx.service.name
                elif tx.product:
                    names[oid] = tx.product.name

        results = [
            OfferingStats(
                offering_id   = oid,
                offering_name = names.get(oid, oid),
                count         = counts[oid],
                total_revenue = revenues[oid],
                total_cost    = costs[oid],
                total_profit  = revenues[oid] - costs[oid],
            )
            for oid in counts
        ]

        return sorted(results, key=lambda x: x.count, reverse=True)[:top]

    # -----------------------------------------------------------------------
    # Clientes
    # -----------------------------------------------------------------------

    def most_frequent_clients(
        self,
        start: datetime,
        end: datetime,
        top: int = 10,
    ) -> list[PersonStats]:
        transactions = self._transactions_in_range(start, end)

        counts: dict[str, int]     = defaultdict(int)
        totals: dict[str, Decimal] = defaultdict(Decimal)
        names:  dict[str, str]     = {}

        for tx in transactions:
            per_person = tx.price_per_person
            clients = [p for p in tx.persons if p.is_recipient]
            for client in clients:
                counts[client.id] += 1
                totals[client.id] += per_person
                names[client.id]   = client.name

        results = [
            PersonStats(
                person_id         = pid,
                person_name       = names[pid],
                transaction_count = counts[pid],
                total_spent       = totals[pid],
                total_generated   = Decimal("0"),
            )
            for pid in counts
        ]

        return sorted(results, key=lambda x: x.transaction_count, reverse=True)[:top]
    
    def most_active_providers(
        self,
        start: datetime,
        end: datetime,
        top: int = 10,
    ) -> list[PersonStats]:
        transactions = self._transactions_in_range(start, end)

        counts: dict[str, int]     = defaultdict(int)
        totals: dict[str, Decimal] = defaultdict(Decimal)
        names:  dict[str, str]     = {}

        for tx in transactions:
            providers = [p for p in tx.persons if p.is_provider]
            for provider in providers:
                counts[provider.id] += 1
                totals[provider.id] += tx.amount
                names[provider.id]   = provider.name

        results = [
            PersonStats(
                person_id         = pid,
                person_name       = names[pid],
                transaction_count = counts[pid],
                total_spent       = Decimal("0"),
                total_generated   = totals[pid],
            )
            for pid in counts
        ]

        return sorted(results, key=lambda x: x.transaction_count, reverse=True)[:top]

    # -----------------------------------------------------------------------
    # Citas
    # -----------------------------------------------------------------------

    def appointment_summary(
        self,
        start: datetime,
        end: datetime,
    ) -> AppointmentSummary:
        appointments = (
            self.session.query(Appointment)
            .filter(
                Appointment.scheduled_at >= start,
                Appointment.scheduled_at <= end,
            )
            .all()
        )

        counts = defaultdict(int)
        for appt in appointments:
            counts[appt.status] += 1

        return AppointmentSummary(
            period_start = start,
            period_end   = end,
            scheduled    = counts[AppointmentStatus.SCHEDULED],
            completed    = counts[AppointmentStatus.COMPLETED],
            cancelled    = counts[AppointmentStatus.CANCELLED],
            no_show      = counts[AppointmentStatus.NO_SHOW],
        )

    # -----------------------------------------------------------------------
    # Exportar
    # -----------------------------------------------------------------------

    def export_transactions_to_dict(
        self,
        start: datetime,
        end: datetime,
    ) -> list[dict]:
        transactions = self._transactions_in_range(start, end)

        return [
            {
                "id":              tx.id,
                "occurred_at":     tx.occurred_at.isoformat(),
                "offering":        (tx.service.name if tx.service else "") or (tx.product.name if tx.product else ""),
                "clients":         ", ".join(c.name for c in tx.persons if c.is_recipient),
                "client_count":    len([c for c in tx.persons if c.is_recipient]),
                "providers":       ", ".join(p.name for p in tx.persons if p.is_provider),
                "amount":          str(tx.amount),
                "price_per_client": str(tx.price_per_person),
                "cost_amount":     str(tx.cost_amount) if tx.cost_amount is not None else "",
                "profit":          str(tx.profit) if tx.profit is not None else "",
                "amount_paid":     str(tx.amount_paid),
                "balance":         str(tx.balance),
                "status":          tx.status.value,
            }
            for tx in transactions
        ]

    def export_payments_to_dict(
        self,
        start: datetime,
        end: datetime,
    ) -> list[dict]:
        payments = self._payments_in_range(start, end)

        return [
            {
                "id":              p.id,
                "paid_at":         p.paid_at.isoformat(),
                "amount":          str(p.amount),
                "method":          p.method.value,
                "is_refund":       p.is_refund,
                "transaction_ids": [tx.id for tx in p.transactions],
                "notes":           p.notes or "",
            }
            for p in payments
        ]