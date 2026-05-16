#!/usr/bin/env python
# coding: utf-8

# <a href="https://colab.research.google.com/github/castaneda-a/gesta/blob/main/gesta_tutorial.ipynb" target="_parent">
#   <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/>
# </a>
# 
# # Gesta — Tutorial
# 
# **Gesta** is a Python library for business administration — appointments, transactions, payments, and reporting in a clean, extensible API.
# 
# This notebook walks you through the full workflow of Gesta using `WellnessStudio`, a ready-to-use extension for integral wellness businesses (massage, yoga, therapy, etc.).
# 
# ---
# 
# ### What we'll cover
# 
# 1. Installation
# 2. Initializing the studio
# 3. Registering clients and providers
# 4. Booking appointments
# 5. Registering transactions
# 6. Registering payments
# 7. Selling products directly
# 8. Reports and metrics
# 9. Handling errors
# 10. Extending Gesta for your own business

# ---
# ## 1. Installation

# In[2]:


#%pip install gesta --quiet


# In[3]:


import gesta
print(f"Gesta version: {gesta.__version__}")


# ---
# ## 2. Initializing the studio
# 
# `WellnessStudio` is a pre-built extension of `Gesta` configured for wellness businesses.
# 
# Calling `setup()` creates the database tables and loads sample services and products.
# We use `sqlite:///:memory:` — an in-memory database that resets when the notebook restarts, perfect for tutorials.

# In[4]:


from gesta.extensions import WellnessStudio

studio = WellnessStudio(db_url="sqlite:///:memory:")
studio.setup(load_sample_data=True)

print("Studio initialized.")
print(f"Database reachable: {studio.ping()}")


# ### Pre-loaded sample data
# 
# `setup()` created the following for you:
# 
# | ID | Name | Price | Cost | Duration |
# |---|---|---|---|---|
# | `svc_masaje_sueco` | Swedish massage | $600 | $150 | 60 min |
# | `svc_masaje_piedras` | Hot stone massage | $800 | $200 | 75 min |
# | `svc_yoga_grupal` | Group yoga class | $120/person | $300 | 60 min |
# | `svc_meditacion` | Meditation session | $100/person | $200 | 45 min |
# | `svc_terapia` | Holistic therapy | $900 | $250 | 90 min |
# | `prd_aceite_lavanda` | Lavender essential oil | $180 | $60 | — |
# | `prd_incienso` | Sandalwood incense | $80 | $25 | — |
# | `prd_vela` | Aromatic candle | $220 | $70 | — |
# | `prd_hierbas` | Relaxing herb mix | $120 | $30 | — |

# ---
# ## 3. Registering clients and providers
# 
# All database operations happen inside a `with studio.session() as s:` block.
# The session automatically commits on success and rolls back on any exception.
# 
# > **Important:** Any access to relationships (`service`, `clients`, `providers`) must happen **inside** the `with` block. Once the block closes the session ends and lazy loading is no longer available. Simple column attributes like `.id`, `.amount`, and `.status` are safe to use outside the block.

# In[5]:


# Register clients — save IDs for use in later cells
with studio.session() as s:
    ana   = studio.add_client(s, name="Ana García",   phone="5551234567", email="ana@mail.com")
    luis  = studio.add_client(s, name="Luis Ramos",   phone="5559876543", email="luis@mail.com")
    sofia = studio.add_client(s, name="Sofía Torres", email="sofia@mail.com")

    ana_id   = ana.id
    luis_id  = luis.id
    sofia_id = sofia.id

    print("Clients registered:")
    print(f"  Ana   — {ana_id[:8]}...")
    print(f"  Luis  — {luis_id[:8]}...")
    print(f"  Sofía — {sofia_id[:8]}...")


# In[6]:


# Register providers
with studio.session() as s:
    marta = studio.add_provider(s, name="Marta López", role="therapist",  email="marta@mail.com")
    pedro = studio.add_provider(s, name="Pedro Soto",  role="instructor", email="pedro@mail.com")

    marta_id = marta.id
    pedro_id = pedro.id

    print("Providers registered:")
    print(f"  Marta (therapist)  — {marta_id[:8]}...")
    print(f"  Pedro (instructor) — {pedro_id[:8]}...")


# In[7]:


# List all clients and providers
# Relationships (roles) must be accessed inside the session
with studio.session() as s:
    clients   = studio.list_clients(s)
    providers = studio.list_providers(s)

    print("Clients:")
    for c in clients:
        print(f"  {c.name} — {c.email}")

    print("\nProviders:")
    for p in providers:
        roles = ", ".join(r.name for r in p.roles)
        print(f"  {p.name} — roles: {roles}")


# ---
# ## 4. Booking appointments
# 
# An `Appointment` is a reservation for a future service. It captures:
# - **who** is attending (clients)
# - **who** is delivering (providers)
# - **what** service
# - **when** it will happen
# 
# Gesta automatically validates that the scheduled time is in the future and that no provider has a conflicting appointment.

# In[8]:


from datetime import datetime, timedelta

next_monday = datetime.now() + timedelta(days=7)

# Book a Swedish massage for Ana with Marta
# Access relationships (service, clients, providers) inside the session
with studio.session() as s:
    appt1 = studio.appointments(s).book(
        service_id   = "svc_masaje_sueco",
        client_ids   = [ana_id],
        provider_ids = [marta_id],
        scheduled_at = next_monday.replace(hour=10, minute=0, second=0),
        notes        = "Client prefers light pressure",
    )
    appt1_id = appt1.id

    print(f"Booked: {appt1.service.name}")
    print(f"  When:     {appt1.scheduled_at.strftime('%A %b %d at %H:%M')}")
    print(f"  Clients:  {[c.name for c in [p for p in appt1.persons if p.is_recipient]]}")
    print(f"  Provider: {[p.name for p in [p for p in appt1.persons if p.is_provider]]}")
    print(f"  Status:   {appt1.status.value}")


# In[9]:


# Book a group yoga class for Ana, Luis, and Sofía with Pedro
# Price is $120 per person — total will be $120 × 3 = $360
with studio.session() as s:
    appt2 = studio.appointments(s).book(
        service_id   = "svc_yoga_grupal",
        client_ids   = [ana_id, luis_id, sofia_id],
        provider_ids = [pedro_id],
        scheduled_at = next_monday.replace(hour=12, minute=0, second=0),
    )
    appt2_id = appt2.id

    print(f"Booked: {appt2.service.name}")
    print(f"  Clients:          {[c.name for c in [p for p in appt2.persons if p.is_recipient]]}")
    print(f"  Price per person: ${appt2.service.price}")


# In[10]:


# List all upcoming appointments
with studio.session() as s:
    upcoming = studio.appointments(s).list_upcoming()

    print(f"Upcoming appointments ({len(upcoming)}):")
    for appt in upcoming:
        clients = ", ".join(c.name for c in [p for p in appt.persons if p.is_recipient])
        print(f"  [{appt.scheduled_at.strftime('%H:%M')}] {appt.service.name} — {clients}")


# ### Rescheduling an appointment

# In[11]:


# Reschedule Ana's massage to 11am instead of 10am
with studio.session() as s:
    appt = studio.appointments(s).reschedule(
        appointment_id = appt1_id,
        new_datetime   = next_monday.replace(hour=11, minute=0, second=0),
    )
    print(f"Rescheduled to: {appt.scheduled_at.strftime('%H:%M')}")


# ---
# ## 5. Registering transactions
# 
# A `Transaction` is a record that a service was delivered or a product was sold. It is distinct from an `Appointment`:
# 
# - An `Appointment` is a **future intention**
# - A `Transaction` is a **past fact**
# 
# The most common flow is `register_from_appointment` — it converts a completed appointment into a transaction and automatically marks the appointment as `COMPLETED`.
# 
# Each transaction tracks:
# - `amount` — total charged (`price × clients`)
# - `cost_amount` — actual cost to the business
# - `profit` — `amount - cost_amount`

# In[12]:


# Register the transaction for Ana's massage
with studio.session() as s:
    tx1 = studio.transactions(s).register_from_appointment(
        appointment_id = appt1_id,
        occurred_at    = datetime.now(),
    )
    tx1_id = tx1.id

    print(f"Transaction: {tx1.offering.name}")
    print(f"  Clients:  {[c.name for c in tx1.clients]}")
    print(f"  Amount:   ${tx1.amount}")
    print(f"  Cost:     ${tx1.cost_amount}")
    print(f"  Profit:   ${tx1.profit}")
    print(f"  Status:   {tx1.status.value}")


# In[13]:


# Register the group yoga transaction
# Amount = $120/person × 3 clients = $360
# Cost   = $300 flat (1 class regardless of how many attend)
with studio.session() as s:
    tx2 = studio.transactions(s).register_from_appointment(
        appointment_id = appt2_id,
        occurred_at    = datetime.now(),
    )
    tx2_id = tx2.id

    print(f"Transaction: {tx2.offering.name}")
    print(f"  Clients:          {[c.name for c in tx2.clients]}")
    print(f"  Amount:           ${tx2.amount}")
    print(f"  Price per client: ${tx2.price_per_client}")
    print(f"  Cost:             ${tx2.cost_amount}")
    print(f"  Profit:           ${tx2.profit}")


# In[14]:


# Applying a discount by overriding the amount
from decimal import Decimal

# Book a new appointment first
with studio.session() as s:
    appt3 = studio.appointments(s).book(
        service_id   = "svc_masaje_sueco",
        client_ids   = [luis_id],
        provider_ids = [marta_id],
        scheduled_at = next_monday.replace(hour=14, minute=0, second=0),
    )
    appt3_id = appt3.id
    print(f"Booked appointment for Luis: {appt3_id[:8]}...")

# Register with 20% discount
with studio.session() as s:
    tx3 = studio.transactions(s).register_from_appointment(
        appointment_id = appt3_id,
        occurred_at    = datetime.now(),
        amount         = Decimal("480.00"),  # $600 - 20% discount
        notes          = "20% loyalty discount applied",
    )
    tx3_id     = tx3.id
    orig_price = tx3.offering.price

    print(f"Discounted transaction: ${tx3.amount} (original price: ${orig_price})")


# ---
# ## 6. Registering payments
# 
# A `Payment` records money received. Key features:
# - One payment can cover **multiple transactions** at once
# - Payments can be **partial** — the transaction stays `PARTIAL` until fully paid
# - Transaction status updates **automatically**: `PENDING` → `PARTIAL` → `PAID`

# In[15]:


from gesta.core.entities import PaymentMethod

# Ana pays for her massage in cash
with studio.session() as s:
    studio.payments(s).register(
        transaction_ids = [tx1_id],
        amount          = Decimal("600.00"),
        method          = PaymentMethod.CASH,
        paid_at         = datetime.now(),
    )

# Check transaction status after payment
with studio.session() as s:
    tx = studio.transactions(s).get(tx1_id)
    print(f"Ana's massage after payment:")
    print(f"  Status:  {tx.status.value}")
    print(f"  Paid:    ${tx.amount_paid}")
    print(f"  Balance: ${tx.balance}")


# In[16]:


# Partial payment for the yoga class
with studio.session() as s:
    studio.payments(s).register(
        transaction_ids = [tx2_id],
        amount          = Decimal("200.00"),  # partial — $360 total
        method          = PaymentMethod.CARD,
        paid_at         = datetime.now(),
        notes           = "First installment",
    )

with studio.session() as s:
    tx = studio.transactions(s).get(tx2_id)
    print(f"Group yoga after partial payment:")
    print(f"  Status:  {tx.status.value}")
    print(f"  Paid:    ${tx.amount_paid}")
    print(f"  Balance: ${tx.balance}")


# In[17]:


# Pay the remaining balance
with studio.session() as s:
    tx    = studio.transactions(s).get(tx2_id)
    remaining = tx.balance

with studio.session() as s:
    studio.payments(s).register(
        transaction_ids = [tx2_id],
        amount          = remaining,
        method          = PaymentMethod.TRANSFER,
        paid_at         = datetime.now(),
        notes           = "Final payment",
    )

with studio.session() as s:
    tx = studio.transactions(s).get(tx2_id)
    print(f"Group yoga after full payment:")
    print(f"  Status:  {tx.status.value}")
    print(f"  Balance: ${tx.balance}")


# In[18]:


# Pay Luis's discounted massage
with studio.session() as s:
    studio.payments(s).register(
        transaction_ids = [tx3_id],
        amount          = Decimal("480.00"),
        method          = PaymentMethod.CARD,
        paid_at         = datetime.now(),
    )
    print("Luis's discounted massage paid.")


# ### Refunds

# In[19]:


# Book, complete, and pay a new transaction — then issue a refund
with studio.session() as s:
    appt_refund = studio.appointments(s).book(
        service_id   = "svc_terapia",
        client_ids   = [sofia_id],
        provider_ids = [marta_id],
        scheduled_at = datetime.now() + timedelta(days=14),
    )
    appt_refund_id = appt_refund.id

with studio.session() as s:
    tx_refund    = studio.transactions(s).register_from_appointment(
        appointment_id = appt_refund_id,
        occurred_at    = datetime.now(),
    )
    tx_refund_id = tx_refund.id

with studio.session() as s:
    studio.payments(s).register(
        transaction_ids = [tx_refund_id],
        amount          = Decimal("900.00"),
        method          = PaymentMethod.CARD,
        paid_at         = datetime.now(),
    )

# Issue the refund
with studio.session() as s:
    studio.payments(s).register_refund(
        transaction_ids = [tx_refund_id],
        amount          = Decimal("900.00"),
        method          = PaymentMethod.CARD,
        paid_at         = datetime.now(),
        notes           = "Client cancelled — full refund",
    )

with studio.session() as s:
    tx = studio.transactions(s).get(tx_refund_id)
    print(f"After refund — status: {tx.status.value}")


# ---
# ## 7. Selling products directly
# 
# Products don't require an appointment. Use `transactions.register()` directly.

# In[20]:


# Ana buys lavender oil and a candle on her way out
# All relationship accesses happen inside the session
with studio.session() as s:
    tx_oil    = studio.transactions(s).register(
        service_id = "prd_aceite_lavanda",
        client_ids  = [ana_id],
        occurred_at = datetime.now(),
    )
    tx_candle = studio.transactions(s).register(
        service_id = "prd_vela",
        client_ids  = [ana_id],
        occurred_at = datetime.now(),
    )
    tx_oil_id      = tx_oil.id
    tx_candle_id   = tx_candle.id
    total_products = tx_oil.amount + tx_candle.amount

    print(f"Lavender oil:    ${tx_oil.amount}  (profit: ${tx_oil.profit})")
    print(f"Aromatic candle: ${tx_candle.amount}  (profit: ${tx_candle.profit})")
    print(f"Total:           ${total_products}")


# In[21]:


# Ana pays for both products in one single cash payment
with studio.session() as s:
    studio.payments(s).register(
        transaction_ids = [tx_oil_id, tx_candle_id],
        amount          = total_products,
        method          = PaymentMethod.CASH,
        paid_at         = datetime.now(),
        notes           = "Products purchased at checkout",
    )
    print(f"Ana paid ${total_products} cash for both products.")


# ---
# ## 8. Reports and metrics
# 
# The `ReportManager` provides aggregated summaries of your business data.
# All report data is accessed inside the session.

# In[22]:


start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
end   = datetime.now()

with studio.session() as s:
    summary = studio.reports(s).monthly_summary(
        year  = datetime.now().year,
        month = datetime.now().month,
    )
    print("Monthly Revenue Summary")
    print(f"  Transactions:  {summary.transaction_count}")
    print(f"  Payments:      {summary.payment_count}")
    print(f"  Total revenue: ${summary.total_revenue}")
    print(f"  Total cost:    ${summary.total_cost}")
    print(f"  Total profit:  ${summary.total_profit}")
    print(f"  Profit margin: {summary.profit_margin}%")
    print(f"  Collected:     ${summary.total_collected}")
    print(f"  Pending:       ${summary.total_pending}")
    print(f"  By method:     {summary.by_method}")


# In[23]:


with studio.session() as s:
    top_offerings = studio.reports(s).most_popular_offerings(
        start = start,
        end   = end,
        top   = 5,
    )
    print("Most popular offerings:")
    for o in top_offerings:
        print(f"  {o.offering_name:<30}  {o.count}x  revenue: ${o.total_revenue}  margin: {o.profit_margin}%")


# In[24]:


with studio.session() as s:
    top_clients = studio.reports(s).most_frequent_clients(
        start = start,
        end   = end,
    )
    print("Most frequent clients:")
    for c in top_clients:
        print(f"  {c.person_name:<20}  {c.transaction_count} transactions  spent: ${c.total_spent:.2f}")


# In[25]:


with studio.session() as s:
    top_providers = studio.reports(s).most_active_providers(
        start = start,
        end   = end,
    )
    print("Most active providers:")
    for p in top_providers:
        print(f"  {p.person_name:<20}  {p.transaction_count} sessions  generated: ${p.total_generated}")


# In[26]:


with studio.session() as s:
    appt_summary = studio.reports(s).appointment_summary(
        start = start,
        end   = end + timedelta(days=30),
    )
    print("Appointment summary:")
    print(f"  Total:           {appt_summary.total}")
    print(f"  Completed:       {appt_summary.completed}")
    print(f"  Scheduled:       {appt_summary.scheduled}")
    print(f"  Cancelled:       {appt_summary.cancelled}")
    print(f"  No-shows:        {appt_summary.no_show}")
    print(f"  Completion rate: {appt_summary.completion_rate}%")


# In[27]:


import json

with studio.session() as s:
    rows = studio.reports(s).export_transactions_to_dict(
        start = start,
        end   = end,
    )
    print(f"Exported {len(rows)} transactions.")
    print("\nFirst transaction:")
    print(json.dumps(rows[0], indent=2))


# ---
# ## 9. Handling errors
# 
# Gesta raises descriptive exceptions that you can catch individually or as a group.
# All exceptions inherit from `GestaError`.

# In[28]:


from gesta import (
    ValidationError,
    AppointmentConflictError,
    NotFoundError,
    BusinessRuleError,
    GestaError,
)

# 1. Scheduling in the past
print("1. Scheduling in the past:")
try:
    with studio.session() as s:
        studio.appointments(s).book(
            service_id   = "svc_masaje_sueco",
            client_ids   = [ana_id],
            provider_ids = [marta_id],
            scheduled_at = datetime.now() - timedelta(days=1),
        )
except ValidationError as e:
    print(f"  ValidationError caught: {e}")


# In[29]:


# 2. Schedule conflict — Marta already has a booking at 11am next Monday
print("2. Schedule conflict:")
try:
    with studio.session() as s:
        studio.appointments(s).book(
            service_id   = "svc_masaje_sueco",
            client_ids   = [sofia_id],
            provider_ids = [marta_id],
            scheduled_at = next_monday.replace(hour=11, minute=30, second=0),
        )
except AppointmentConflictError as e:
    print(f"  AppointmentConflictError caught: {e}")


# In[30]:


# 3. Entity not found
print("3. Entity not found:")
try:
    with studio.session() as s:
        studio.appointments(s).get("non-existent-id")
except NotFoundError as e:
    print(f"  NotFoundError caught: {e}")
    print(f"  Entity: {e.entity}, ID: {e.identifier}")


# In[31]:


# 4. Cancelling an appointment that has a transaction
print("4. Cancelling an appointment with a transaction:")
try:
    with studio.session() as s:
        studio.appointments(s).cancel(appt1_id)
except BusinessRuleError as e:
    print(f"  BusinessRuleError caught: {e}")


# ---
# ## 10. Extending Gesta for your own business
# 
# Gesta is designed to adapt to any appointment-based business.
# Create your own extension by subclassing `Gesta` and defining your roles and services.

# In[32]:


import uuid
from gesta import Gesta
from gesta.core.entities import Role, Person, Service, OfferingStats
from decimal import Decimal

class HairSalon(Gesta):
    """A simple hair salon extension."""

    def setup(self):
        with self.session() as s:
            for role_data in [
                {"id": "salon_client",  "name": "client",  "is_recipient": True,  "is_provider": False},
                {"id": "salon_stylist", "name": "stylist", "is_recipient": False, "is_provider": True},
            ]:
                if not s.get(Role, role_data["id"]):
                    s.add(Role(**role_data))

            if not s.get(Service, "svc_haircut"):
                s.add(Service(
                    id="svc_haircut", type=OfferingStats.SERVICE,
                    name="Haircut", price=Decimal("350.00"), cost=Decimal("80.00"),
                    duration_min="45", requires_space=True, is_active=True,
                ))

    def add_client(self, session, name, email=None):
        role   = session.query(Role).filter(Role.id == "salon_client").first()
        person = Person(id=str(uuid.uuid4()), name=name, email=email)
        person.roles = [role]
        session.add(person)
        return person

    def add_stylist(self, session, name, email=None):
        role   = session.query(Role).filter(Role.id == "salon_stylist").first()
        person = Person(id=str(uuid.uuid4()), name=name, email=email)
        person.roles = [role]
        session.add(person)
        return person


salon = HairSalon(db_url="sqlite:///:memory:")
salon.setup()

with salon.session() as s:
    client  = salon.add_client(s, name="María Pérez", email="maria@mail.com")
    stylist = salon.add_stylist(s, name="Carlos Vega", email="carlos@mail.com")
    client_id  = client.id
    stylist_id = stylist.id

with salon.session() as s:
    appt = salon.appointments(s).book(
        service_id   = "svc_haircut",
        client_ids   = [client_id],
        provider_ids = [stylist_id],
        scheduled_at = datetime.now() + timedelta(days=2),
    )
    print(f"Booked: {appt.service.name} for {[p for p in appt.persons if p.is_recipient][0].name}")
    print(f"  Price:  ${appt.service.price}")
    print(f"  Margin: ${appt.service.margin}")


# ---
# ## Summary
# 
# You've seen the full Gesta workflow:
# 
# | Step | What happens |
# |---|---|
# | `studio.setup()` | Initialize database, roles, and sample data |
# | `add_client / add_provider` | Register people with roles |
# | `appointments.book()` | Create a future reservation |
# | `appointments.reschedule()` | Change the date/time |
# | `transactions.register_from_appointment()` | Deliver the service → creates transaction |
# | `transactions.register()` | Direct sale without appointment |
# | `payments.register()` | Record money received |
# | `payments.register_refund()` | Issue a refund |
# | `reports.monthly_summary()` | Revenue, cost, profit overview |
# | `reports.most_popular_offerings()` | Top services and products |
# | `reports.export_transactions_to_dict()` | Export data to CSV/JSON |
# 
# ---
# 
# ### Resources
# 
# - **PyPI**: https://pypi.org/project/gesta
# - **GitHub**: https://github.com/castaneda-a/gesta
# - **License**: MIT
