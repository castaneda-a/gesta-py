# =============================================================================
# scripts/demo.py
# =============================================================================
# End-to-end demo of Gesta using WellnessStudio.
# Runs entirely in memory — no files created.
# =============================================================================

from datetime import datetime, timedelta
from decimal import Decimal

from gesta.extensions import WellnessStudio
from gesta.core.entities import PaymentMethod


def separator(title: str) -> None:
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║              Gesta — Demo                        ║")
    print("╚══════════════════════════════════════════════════╝")

    # -----------------------------------------------------------------------
    # Setup
    # -----------------------------------------------------------------------
    studio = WellnessStudio(db_url="sqlite:///:memory:")
    studio.setup(load_sample_data=True)
    print("\n✓ WellnessStudio initialized with sample data")

    # -----------------------------------------------------------------------
    # Register people
    # -----------------------------------------------------------------------
    separator("Registering people")

    with studio.session() as s:
        ana   = studio.add_client(s,   name="Ana García",   phone="5551234567", email="ana@mail.com")
        luis  = studio.add_client(s,   name="Luis Ramos",   phone="5559876543", email="luis@mail.com")
        marta = studio.add_provider(s, name="Marta López",  role="therapist",   email="marta@mail.com")
        pedro = studio.add_provider(s, name="Pedro Soto",   role="instructor",  email="pedro@mail.com")

        ana_id   = ana.id
        luis_id  = luis.id
        marta_id = marta.id
        pedro_id = pedro.id

    print(f"  Client:     Ana García")
    print(f"  Client:     Luis Ramos")
    print(f"  Therapist:  Marta López")
    print(f"  Instructor: Pedro Soto")

    # -----------------------------------------------------------------------
    # Book appointments
    # -----------------------------------------------------------------------
    separator("Booking appointments")

    next_monday = datetime.now() + timedelta(days=7)

    with studio.session() as s:
        appt1 = studio.appointments(s).book(
            service_id   = "svc_masaje_sueco",
            client_ids   = [ana_id],
            provider_ids = [marta_id],
            scheduled_at = next_monday.replace(hour=10, minute=0),
            notes        = "Client prefers light pressure",
        )
        appt1_id = appt1.id

    print(f"  Booked: Ana — Swedish massage with Marta on {next_monday.strftime('%A %b %d')} at 10:00")

    with studio.session() as s:
        appt2 = studio.appointments(s).book(
            service_id   = "svc_yoga_grupal",
            client_ids   = [ana_id, luis_id],
            provider_ids = [pedro_id],
            scheduled_at = next_monday.replace(hour=12, minute=0),
        )
        appt2_id = appt2.id

    print(f"  Booked: Ana + Luis — Group yoga with Pedro on {next_monday.strftime('%A %b %d')} at 12:00")

    # -----------------------------------------------------------------------
    # Register transactions
    # -----------------------------------------------------------------------
    separator("Registering transactions")

    with studio.session() as s:
        tx1 = studio.transactions(s).register_from_appointment(
            appointment_id = appt1_id,
            occurred_at    = datetime.now(),
        )
        tx1_id = tx1.id
        print(f"  Transaction: Ana — Swedish massage")
        print(f"    Amount:  ${tx1.amount}")
        print(f"    Cost:    ${tx1.cost_amount}")
        print(f"    Profit:  ${tx1.profit}")

    with studio.session() as s:
        tx2 = studio.transactions(s).register_from_appointment(
            appointment_id = appt2_id,
            occurred_at    = datetime.now(),
        )
        tx2_id = tx2.id
        print(f"  Transaction: Ana + Luis — Group yoga (2 clients)")
        print(f"    Amount:  ${tx2.amount}  (${tx2.price_per_person}/client)")
        print(f"    Cost:    ${tx2.cost_amount}")
        print(f"    Profit:  ${tx2.profit}")

    # -----------------------------------------------------------------------
    # Register payments
    # -----------------------------------------------------------------------
    separator("Registering payments")

    # Ana pays for her massage in cash
    with studio.session() as s:
        p1 = studio.payments(s).register(
            transaction_ids = [tx1_id],
            amount          = Decimal("600.00"),
            method          = PaymentMethod.CASH,
            paid_at         = datetime.now(),
        )
    print(f"  Ana paid $600.00 cash for massage")

    # Ana and Luis pay for yoga together with one card payment
    with studio.session() as s:
        p2 = studio.payments(s).register(
            transaction_ids = [tx2_id],
            amount          = Decimal("240.00"),
            method          = PaymentMethod.CARD,
            paid_at         = datetime.now(),
        )
    print(f"  Ana + Luis paid $240.00 card for yoga")

    # -----------------------------------------------------------------------
    # Sell a product (no appointment needed)
    # -----------------------------------------------------------------------
    separator("Direct product sale")

    with studio.session() as s:
        tx3 = studio.transactions(s).register(
            product_id   = "prd_aceite_lavanda",
            client_ids   = [ana_id],
            occurred_at  = datetime.now(),
        )
        tx3_id = tx3.id
        print(f"  Ana bought lavender oil — ${tx3.amount}")

    with studio.session() as s:
        studio.payments(s).register(
            transaction_ids = [tx3_id],
            amount          = Decimal("180.00"),
            method          = PaymentMethod.CASH,
            paid_at         = datetime.now(),
        )
    print(f"  Paid $180.00 cash")

    # -----------------------------------------------------------------------
    # Reports
    # -----------------------------------------------------------------------
    separator("Monthly revenue report")

    with studio.session() as s:
        summary = studio.reports(s).monthly_summary(
            year  = datetime.now().year,
            month = datetime.now().month,
        )

    print(f"  Transactions:  {summary.transaction_count}")
    print(f"  Payments:      {summary.payment_count}")
    print(f"  Total revenue: ${summary.total_revenue}")
    print(f"  Total cost:    ${summary.total_cost}")
    print(f"  Total profit:  ${summary.total_profit}")
    print(f"  Profit margin: {summary.profit_margin}%")
    print(f"  Collected:     ${summary.total_collected}")
    print(f"  Pending:       ${summary.total_pending}")
    print(f"  By method:     {summary.by_method}")

    separator("Most popular offerings")

    with studio.session() as s:
        offerings = studio.reports(s).most_popular_offerings(
            start = datetime.now().replace(day=1, hour=0, minute=0, second=0),
            end   = datetime.now(),
            top   = 3,
        )

    for o in offerings:
        print(f"  {o.offering_name:<30} {o.count}x   revenue: ${o.total_revenue}   margin: {o.profit_margin}%")

    separator("Most frequent clients")

    with studio.session() as s:
        clients = studio.reports(s).most_frequent_clients(
            start = datetime.now().replace(day=1, hour=0, minute=0, second=0),
            end   = datetime.now(),
            top   = 5,
        )

    for c in clients:
        print(f"  {c.person_name:<20} {c.transaction_count} transactions   spent: ${c.total_spent}")

    print("\n✓ Demo complete\n")


if __name__ == "__main__":
    main()