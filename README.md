# Gesta

A Python library for hanling Gesta, a Customer Relationship Manager (CRM) — appointments, transactions, payments, and reporting in a clean, extensible API.

---

## Tutorial
For a detailed notebook tutorial, visit the following link:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/castaneda-a/gesta/blob/main/gesta_tutorial.ipynb)


---

## Features

- **Appointment management** — book, reschedule, cancel, and complete appointments with conflict detection
- **Transaction tracking** — register services rendered and products sold, with cost and profit tracking
- **Payment management** — register payments against one or multiple transactions, including partial payments and refunds
- **Reporting** — revenue summaries, profit margins, popular offerings, frequent clients, and more
- **Extensible** — adapt Gesta to any business type by extending the base `Gesta` class
- **SQLite & PostgreSQL** — works locally out of the box, ready for production with Postgres

---

## Installation

```bash
pip install gesta
```

Requires Python 3.12+.

---

## Quick start

```python
from datetime import datetime, timedelta
from gesta.extensions import WellnessStudio

# Initialize — creates the database and tables automatically
studio = WellnessStudio(db_url="sqlite:///my_business.db")
studio.setup()

# Register a client and a provider
with studio.session() as s:
    client    = studio.add_client(s, name="Ana García",  phone="5551234567")
    therapist = studio.add_provider(s, name="Marta López", role="therapist")

# Book an appointment
with studio.session() as s:
    ana   = studio.list_clients(s)[0]
    marta = studio.list_providers(s)[0]

    appointment = studio.appointments(s).book(
        service_id   = "svc_masaje_sueco",
        client_ids   = [ana.id],
        provider_ids = [marta.id],
        scheduled_at = datetime.now() + timedelta(days=3),
    )

# Register the transaction when the service is delivered
with studio.session() as s:
    tx = studio.transactions(s).register_from_appointment(
        appointment_id = appointment.id,
        occurred_at    = datetime.now(),
    )

# Register payment
with studio.session() as s:
    from gesta.core.entities import PaymentMethod
    studio.payments(s).register(
        transaction_ids = [tx.id],
        amount          = tx.amount,
        method          = PaymentMethod.CASH,
        paid_at         = datetime.now(),
    )

# Monthly revenue report
with studio.session() as s:
    summary = studio.reports(s).monthly_summary(
        year  = datetime.now().year,
        month = datetime.now().month,
    )
    print(f"Revenue:   ${summary.total_revenue}")
    print(f"Collected: ${summary.total_collected}")
    print(f"Profit:    ${summary.total_profit}")
    print(f"Margin:    {summary.profit_margin}%")
```

---

## Core concepts

### Entities

| Entity | Description |
|---|---|
| `Person` | Any participant — client, therapist, instructor, etc. |
| `Role` | What role a person plays (`is_provider`, `is_recipient`) |
| `Service` | An offering that requires scheduling and a provider |
| `Product` | A physical offering with inventory |
| `Appointment` | A future reservation of a service |
| `Transaction` | A record that a service was delivered or a product was sold |
| `Payment` | A money movement linked to one or more transactions |


### Attributes of entities

#### Person
| persons | Data type | Nullable |
|---|---|---|
| `id` | String | primary key |
| `name` | String(120) | F |
| `email` | String(120) | T | 
| `phone` | String(30) | T |
| `notes` | Text | T | 
| `created_at` | DateTime | F |
| `updated_at` | DateTime | F |

#### Role
| roles | Data type | Nullable |
|---|---|---|
| `id` | String | primary key |
| `name` | String(120) | F |
| `description` | Text | T | 
| `is_provider` | Boolean | F |
| `is_recipient` | Boolean | F |

#### Offering
| offerings | Data type | Nullable |
|---|---|---|
| `id` | String | primary key |
| `type` | OfferingType | F |
| `name` | String(120) | F |
| `description` | Text | T | 
| `price` | Numeric(10,2) | F |
| `cost` | Numeric(10,2) | T |
| `is_active` | Boolean | F |
| `created_at` | DateTime | F |

donde OfferingType:
1. SERVICE
2. PRODUCT


#### Appointment
| appointments | Data type | Nullable |
|---|---|---|
| `id` | String | primary key |
| `service_id` | String | foreign key |
| `status` | AppointmentStatus | F |
| `scheduled_at` | DateTime | F |
| `registered_at` | DateTime | F |
| `notes` | Text | T | 

donde AppointmentStatus:
1. SCHEDULED
2. COMPLETED
3. CANCELLED
4. NO_SHOW


#### Transaction
| transactions | Data type | Nullable |
|---|---|---|
| `id` | String | primary key |
| `appointment_id` | String | foreign key |
| `offering_id` | String | foreign key |
| `amount` | Numeric(10,2) | F |
| `cost_amount` | Numeric(10,2) | T |
| `status` | TransactionStatus | F |
| `occurred_at` | DateTime | F |
| `created_at` | DateTime | F |
| `notes` | Text | T | 

donde TransactionStatus:
1. PENDING
2. PAID
3. PARTIAL
4. REFUNDED


#### Payment
| payments | Data type | Nullable |
|---|---|---|
| `id` | String | primary key |
| `amount` | Numeric(10,2) | F |
| `method` | PaymentMethod | F |
| `is_refund` | Boolean | F |
| `paid_at` | DateTime | F |
| `created_at` | DateTime | F |
| `notes` | Text | T | 

donde PaymentMethod:
1. CASH
2. CARD
3. TRANSFER
4. OTHER


### Transaction vs Appointment

These are two distinct events in time:

```
Monday 10am  →  Ana books a massage for Thursday     =  Appointment
Thursday 3pm →  Marta gives Ana the massage           =  Transaction
Thursday 3pm →  Ana pays $600 cash                   =  Payment (direct)

— or —

Thursday 3pm →  Ana doesn't pay that day             =  Payment pending
Friday 11am  →  Ana transfers $600                   =  Payment (indirect)
```

### Price, cost, and profit

Every `Service` and `Product` has:
- `price` — what the client pays (per person / per unit)
- `cost`  — what it costs the business to deliver
- `margin` — `price - cost` (property, computed automatically)

Every `Transaction` tracks:
- `amount` — total charged (`price × number of clients`)
- `cost_amount` — actual cost at the time of the transaction
- `profit` — `amount - cost_amount` (property)

---
## API Reference

### `Gesta` — main class

The entry point of the library. Manages the database connection and exposes all managers.

---

#### `Gesta(db_url, echo=False)`

Initializes the library, connects to the database, and creates all tables if they don't exist.

| Parameter | Type | Description |
|---|---|---|
| `db_url` | `str` | SQLAlchemy connection URL |
| `echo` | `bool` | If `True`, prints generated SQL. Useful during development. |

```python
from gesta import Gesta

# SQLite — local file
studio = Gesta(db_url="sqlite:///business.db")

# SQLite — in memory (useful for tests)
studio = Gesta(db_url="sqlite:///:memory:")

# PostgreSQL
studio = Gesta(db_url="postgresql://user:password@localhost/gesta_db")

# With SQL logging enabled
studio = Gesta(db_url="sqlite:///business.db", echo=True)
```

---

#### `Gesta.session()`

Context manager that provides a database session. Automatically commits on success and rolls back on exception.

```python
# All operations inside one session are committed together.
# If any fails, all are rolled back.
with studio.session() as s:
    appt = studio.appointments(s).book(...)
    tx   = studio.transactions(s).register_from_appointment(appt.id, ...)
    studio.payments(s).register([tx.id], ...)
```

---

#### `Gesta.ping()`

Returns `True` if the database is reachable, `False` otherwise.

```python
if studio.ping():
    print("Database is up")
else:
    print("Cannot reach database")
```

---

### `AppointmentManager` — `studio.appointments(session)`

Manages the full lifecycle of appointments.

---

#### `.book(service_id, client_ids, scheduled_at, provider_ids=None, notes=None)`

Creates a new appointment in `SCHEDULED` status.

Validates that `scheduled_at` is in the future, the service is active, all clients have a recipient role, all providers have a provider role, and no provider has a schedule conflict.

| Parameter | Type | Description |
|---|---|---|
| `service_id` | `str` | ID of the service to book |
| `client_ids` | `list[str]` | IDs of clients attending |
| `scheduled_at` | `datetime` | Date and time of the appointment |
| `provider_ids` | `list[str]` | IDs of providers delivering the service |
| `notes` | `str` | Optional notes |

```python
from datetime import datetime, timedelta

with studio.session() as s:
    # Single client, single provider
    appt = studio.appointments(s).book(
        service_id   = "svc_masaje_sueco",
        client_ids   = ["client_id_1"],
        provider_ids = ["provider_id_1"],
        scheduled_at = datetime.now() + timedelta(days=3),
        notes        = "Client prefers light pressure",
    )

    # Group class — multiple clients
    appt = studio.appointments(s).book(
        service_id   = "svc_yoga_grupal",
        client_ids   = ["client_id_1", "client_id_2", "client_id_3"],
        provider_ids = ["instructor_id_1"],
        scheduled_at = datetime.now() + timedelta(days=1),
    )
```

---

#### `.get(appointment_id)`

Returns an appointment by ID. Raises `NotFoundError` if it doesn't exist.

```python
with studio.session() as s:
    appt = studio.appointments(s).get("appt_id_123")
    print(appt.status)
    print(appt.scheduled_at)
```

---

#### `.reschedule(appointment_id, new_datetime)`

Changes the date and time of a `SCHEDULED` appointment. Validates the new datetime is in the future and checks for provider conflicts.

```python
with studio.session() as s:
    studio.appointments(s).reschedule(
        appointment_id = "appt_id_123",
        new_datetime   = datetime.now() + timedelta(days=5),
    )
```

---

#### `.cancel(appointment_id)`

Marks an appointment as `CANCELLED`. Raises `BusinessRuleError` if the appointment already has a transaction associated.

```python
with studio.session() as s:
    studio.appointments(s).cancel("appt_id_123")
```

---

#### `.complete(appointment_id)`

Marks an appointment as `COMPLETED`. Normally called automatically by `register_from_appointment`, but can be used manually.

```python
with studio.session() as s:
    studio.appointments(s).complete("appt_id_123")
```

---

#### `.mark_no_show(appointment_id)`

Marks an appointment as `NO_SHOW` — the client did not show up.

```python
with studio.session() as s:
    studio.appointments(s).mark_no_show("appt_id_123")
```

---

#### `.list_upcoming()`

Returns all future appointments in `SCHEDULED` status, ordered by date.

```python
with studio.session() as s:
    upcoming = studio.appointments(s).list_upcoming()
    for appt in upcoming:
        print(f"{appt.scheduled_at}  —  {appt.service.name}")
```

---

#### `.list_by_date(date)`

Returns all appointments on a given day.

```python
with studio.session() as s:
    today = studio.appointments(s).list_by_date(datetime.now())
```

---

#### `.list_by_client(client_id)`

Returns all appointments for a given client, ordered by date descending.

```python
with studio.session() as s:
    appts = studio.appointments(s).list_by_client("client_id_1")
```

---

#### `.list_by_provider(provider_id)`

Returns all appointments for a given provider, ordered by date descending.

```python
with studio.session() as s:
    appts = studio.appointments(s).list_by_provider("provider_id_1")
```

---

#### `.list_by_status(status)`

Returns all appointments with a given status.

```python
from gesta.core.entities import AppointmentStatus

with studio.session() as s:
    cancelled = studio.appointments(s).list_by_status(AppointmentStatus.CANCELLED)
```

---

### `TransactionManager` — `studio.transactions(session)`

Manages the registration of services delivered and products sold.

---

#### `.register(offering_id, client_ids, occurred_at, provider_ids=None, amount=None, cost_amount=None, notes=None)`

Registers a direct transaction without a prior appointment. Useful for spontaneous product sales or walk-in services.

If `amount` is not provided, it is calculated as `offering.price × number of clients`.
If `cost_amount` is not provided, it is calculated as `offering.cost × number of clients`.

| Parameter | Type | Description |
|---|---|---|
| `offering_id` | `str` | ID of the service or product |
| `client_ids` | `list[str]` | IDs of clients |
| `occurred_at` | `datetime` | When the service was delivered or product sold |
| `provider_ids` | `list[str]` | IDs of providers (optional for products) |
| `amount` | `Decimal` | Override the calculated amount (e.g. for discounts) |
| `cost_amount` | `Decimal` | Override the calculated cost |
| `notes` | `str` | Optional notes |

```python
from datetime import datetime
from decimal import Decimal

with studio.session() as s:
    # Product sale — no provider needed
    tx = studio.transactions(s).register(
        offering_id = "prd_aceite_lavanda",
        client_ids  = ["client_id_1"],
        occurred_at = datetime.now(),
    )

    # Service with custom discount
    tx = studio.transactions(s).register(
        offering_id  = "svc_masaje_sueco",
        client_ids   = ["client_id_1"],
        provider_ids = ["provider_id_1"],
        occurred_at  = datetime.now(),
        amount       = Decimal("500.00"),  # discounted from $600
    )

    # Group class — amount calculated automatically
    # yoga $120/person × 3 clients = $360
    tx = studio.transactions(s).register(
        offering_id  = "svc_yoga_grupal",
        client_ids   = ["client_1", "client_2", "client_3"],
        provider_ids = ["instructor_id_1"],
        occurred_at  = datetime.now(),
    )
    print(tx.amount)           # Decimal('360.00')
    print(tx.price_per_client) # Decimal('120.00')
    print(tx.profit)           # amount - cost_amount
```

---

#### `.register_from_appointment(appointment_id, occurred_at, amount=None, cost_amount=None, notes=None)`

Registers a transaction from an existing appointment, inheriting its clients, providers, and service. Automatically marks the appointment as `COMPLETED`.

Raises `ValidationError` if the appointment is not in `SCHEDULED` status, and `BusinessRuleError` if it already has a transaction.

```python
with studio.session() as s:
    tx = studio.transactions(s).register_from_appointment(
        appointment_id = "appt_id_123",
        occurred_at    = datetime.now(),
    )
    print(tx.amount)      # price × number of clients
    print(tx.cost_amount) # cost × number of clients
    print(tx.profit)      # amount - cost_amount
```

---

#### `.get(transaction_id)`

Returns a transaction by ID. Raises `NotFoundError` if it doesn't exist.

```python
with studio.session() as s:
    tx = studio.transactions(s).get("tx_id_123")
    print(f"Balance pending: ${tx.balance}")
```

---

#### `.list_by_client(client_id)`

Returns all transactions for a given client.

```python
with studio.session() as s:
    txs = studio.transactions(s).list_by_client("client_id_1")
```

---

#### `.list_by_provider(provider_id)`

Returns all transactions for a given provider.

```python
with studio.session() as s:
    txs = studio.transactions(s).list_by_provider("provider_id_1")
```

---

#### `.list_by_date_range(start, end)`

Returns all transactions within a date range.

```python
with studio.session() as s:
    txs = studio.transactions(s).list_by_date_range(
        start = datetime(2025, 1, 1),
        end   = datetime(2025, 3, 31),
    )
```

---

#### `.list_pending()`

Returns all transactions with unpaid balance (`PENDING` status).

```python
with studio.session() as s:
    pending = studio.transactions(s).list_pending()
    for tx in pending:
        print(f"{tx.id}  —  balance: ${tx.balance}")
```

---

### `PaymentManager` — `studio.payments(session)`

Manages payments linked to one or more transactions.

---

#### `.register(transaction_ids, amount, method, paid_at, notes=None)`

Registers a payment and links it to one or more transactions. Automatically updates the status of each transaction (`PENDING` → `PARTIAL` → `PAID`).

| Parameter | Type | Description |
|---|---|---|
| `transaction_ids` | `list[str]` | IDs of transactions this payment covers |
| `amount` | `Decimal` | Amount paid |
| `method` | `PaymentMethod` | `CASH`, `CARD`, `TRANSFER`, or `OTHER` |
| `paid_at` | `datetime` | When the payment was received |
| `notes` | `str` | Optional notes |

```python
from decimal import Decimal
from datetime import datetime
from gesta.core.entities import PaymentMethod

with studio.session() as s:
    # Full payment — single transaction
    studio.payments(s).register(
        transaction_ids = ["tx_id_1"],
        amount          = Decimal("600.00"),
        method          = PaymentMethod.CASH,
        paid_at         = datetime.now(),
    )

    # Partial payment
    studio.payments(s).register(
        transaction_ids = ["tx_id_1"],
        amount          = Decimal("300.00"),
        method          = PaymentMethod.CARD,
        paid_at         = datetime.now(),
        notes           = "First installment",
    )

    # One payment covers two transactions at once
    studio.payments(s).register(
        transaction_ids = ["tx_id_1", "tx_id_2"],
        amount          = Decimal("780.00"),
        method          = PaymentMethod.TRANSFER,
        paid_at         = datetime.now(),
    )
```

---

#### `.register_refund(transaction_ids, amount, method, paid_at, notes=None)`

Registers a refund against one or more transactions. Marks each transaction as `REFUNDED`.

```python
with studio.session() as s:
    studio.payments(s).register_refund(
        transaction_ids = ["tx_id_1"],
        amount          = Decimal("600.00"),
        method          = PaymentMethod.CASH,
        paid_at         = datetime.now(),
        notes           = "Client was unsatisfied",
    )
```

---

#### `.get(payment_id)`

Returns a payment by ID. Raises `NotFoundError` if it doesn't exist.

```python
with studio.session() as s:
    payment = studio.payments(s).get("pay_id_123")
    print(payment.method)
    print(payment.amount)
```

---

#### `.list_by_transaction(transaction_id)`

Returns all payments associated with a transaction.

```python
with studio.session() as s:
    payments = studio.payments(s).list_by_transaction("tx_id_1")
```

---

#### `.list_by_method(method)`

Returns all payments by payment method.

```python
from gesta.core.entities import PaymentMethod

with studio.session() as s:
    cash_payments = studio.payments(s).list_by_method(PaymentMethod.CASH)
```

---

#### `.list_by_date_range(start, end)`

Returns all payments within a date range.

```python
with studio.session() as s:
    payments = studio.payments(s).list_by_date_range(
        start = datetime(2025, 1, 1),
        end   = datetime(2025, 1, 31),
    )
```

---

### `ReportManager` — `studio.reports(session)`

Generates financial summaries and business metrics. Read-only — never writes data.

---

#### `.revenue_summary(start, end)`

Returns a `RevenueSummary` with full financial breakdown for a period.

| Field | Description |
|---|---|
| `total_revenue` | Sum of all transaction amounts |
| `total_cost` | Sum of all transaction costs |
| `total_profit` | `total_revenue - total_cost` |
| `total_collected` | Sum of payments actually received |
| `total_pending` | Sum of unpaid balances |
| `by_method` | Dict of collected amounts per payment method |
| `transaction_count` | Number of transactions |
| `payment_count` | Number of payments |
| `profit_margin` | Profit as a percentage of revenue |

```python
with studio.session() as s:
    summary = studio.reports(s).revenue_summary(
        start = datetime(2025, 1, 1),
        end   = datetime(2025, 12, 31),
    )
    print(f"Revenue:  ${summary.total_revenue}")
    print(f"Profit:   ${summary.total_profit}")
    print(f"Margin:   {summary.profit_margin}%")
    print(f"Pending:  ${summary.total_pending}")
    print(f"By method: {summary.by_method}")
    # {'cash': Decimal('1200.00'), 'card': Decimal('840.00')}
```

---

#### `.monthly_summary(year, month)`

Shortcut for `revenue_summary` scoped to a single month.

```python
with studio.session() as s:
    summary = studio.reports(s).monthly_summary(year=2025, month=3)
    print(f"March revenue: ${summary.total_revenue}")
```

---

#### `.daily_revenue(start, end)`

Returns a dict of `{ 'YYYY-MM-DD': amount }` for each day in the range.

```python
with studio.session() as s:
    daily = studio.reports(s).daily_revenue(
        start = datetime(2025, 3, 1),
        end   = datetime(2025, 3, 31),
    )
    for day, amount in daily.items():
        print(f"{day}: ${amount}")
```

---

#### `.most_popular_offerings(start, end, top=5)`

Returns the top N most sold services/products in a period, ordered by transaction count.

Each result is an `OfferingStats` with `offering_name`, `count`, `total_revenue`, `total_cost`, `total_profit`, and `profit_margin`.

```python
with studio.session() as s:
    top = studio.reports(s).most_popular_offerings(
        start = datetime(2025, 1, 1),
        end   = datetime(2025, 12, 31),
        top   = 3,
    )
    for item in top:
        print(f"{item.offering_name}: {item.count}x — margin {item.profit_margin}%")
```

---

#### `.most_frequent_clients(start, end, top=10)`

Returns the top N clients by number of transactions. Each result is a `PersonStats` with `person_name`, `transaction_count`, and `total_spent`.

```python
with studio.session() as s:
    clients = studio.reports(s).most_frequent_clients(
        start = datetime(2025, 1, 1),
        end   = datetime(2025, 12, 31),
        top   = 5,
    )
    for c in clients:
        print(f"{c.person_name}: {c.transaction_count} visits — spent ${c.total_spent}")
```

---

#### `.most_active_providers(start, end, top=10)`

Returns the top N providers by number of transactions. Each result is a `PersonStats` with `person_name`, `transaction_count`, and `total_generated`.

```python
with studio.session() as s:
    providers = studio.reports(s).most_active_providers(
        start = datetime(2025, 1, 1),
        end   = datetime(2025, 12, 31),
    )
    for p in providers:
        print(f"{p.person_name}: {p.transaction_count} sessions — generated ${p.total_generated}")
```

---

#### `.appointment_summary(start, end)`

Returns an `AppointmentSummary` with counts per status and completion rate.

| Field | Description |
|---|---|
| `scheduled` | Appointments still pending |
| `completed` | Appointments completed |
| `cancelled` | Appointments cancelled |
| `no_show` | Appointments where client didn't show |
| `total` | Total appointments (property) |
| `completion_rate` | Percentage of completed vs total (property) |

```python
with studio.session() as s:
    summary = studio.reports(s).appointment_summary(
        start = datetime(2025, 1, 1),
        end   = datetime(2025, 12, 31),
    )
    print(f"Completed:       {summary.completed}/{summary.total}")
    print(f"Completion rate: {summary.completion_rate}%")
    print(f"No-shows:        {summary.no_show}")
```

---

#### `.export_transactions_to_dict(start, end)`

Exports transactions in a period as a list of dicts, ready to convert to CSV or JSON.

```python
import json, csv

with studio.session() as s:
    rows = studio.reports(s).export_transactions_to_dict(
        start = datetime(2025, 1, 1),
        end   = datetime(2025, 12, 31),
    )

# Export to JSON
with open("transactions.json", "w") as f:
    json.dump(rows, f, indent=2)

# Export to CSV
with open("transactions.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
```

---

#### `.export_payments_to_dict(start, end)`

Exports payments in a period as a list of dicts.

```python
with studio.session() as s:
    rows = studio.reports(s).export_payments_to_dict(
        start = datetime(2025, 1, 1),
        end   = datetime(2025, 12, 31),
    )
```

---

### `WellnessStudio` — `gesta.extensions.WellnessStudio`

A ready-to-use extension of `Gesta` for integral wellness businesses. Preloads roles, sample services, and sample products.

---

#### `WellnessStudio(db_url, echo=False)`

Same as `Gesta`, with wellness-specific setup.

```python
from gesta.extensions import WellnessStudio

studio = WellnessStudio(db_url="sqlite:///wellness.db")
```

---

#### `.setup(load_sample_data=True)`

Initializes roles and optionally loads sample services and products. Safe to call multiple times — never duplicates records.

Set `load_sample_data=False` for production to load only roles.

```python
studio.setup()                          # loads roles + sample data
studio.setup(load_sample_data=False)    # loads roles only
```

**Predefined roles:** `client`, `therapist`, `instructor`, `admin`

**Sample services:** Swedish massage, hot stone massage, group yoga, meditation session, holistic therapy

**Sample products:** Lavender essential oil, sandalwood incense, aromatic candle, relaxing herb mix

---

#### `.add_client(session, name, phone=None, email=None, notes=None)`

Registers a new person with the `client` role. Raises `DuplicateError` if the email already exists.

```python
with studio.session() as s:
    client = studio.add_client(
        s,
        name  = "Ana García",
        phone = "5551234567",
        email = "ana@mail.com",
    )
    print(client.id)
```

---

#### `.add_provider(session, name, role, phone=None, email=None, notes=None)`

Registers a new person with a provider role (`therapist`, `instructor`, or `admin`). Raises `DuplicateError` if the email already exists, and `InvalidRoleError` if the role is not a provider role.

```python
with studio.session() as s:
    therapist = studio.add_provider(
        s,
        name  = "Marta López",
        role  = "therapist",
        email = "marta@mail.com",
    )
```

---

#### `.list_clients(session)`

Returns all active people with the `client` role, ordered by name.

```python
with studio.session() as s:
    clients = studio.list_clients(s)
    for c in clients:
        print(c.name)
```

---

#### `.list_providers(session)`

Returns all active people with a provider role, ordered by name.

```python
with studio.session() as s:
    providers = studio.list_providers(s)
```

---

### Exceptions

All exceptions inherit from `GestaError` and can be caught individually or as a group.

| Exception | When it's raised |
|---|---|
| `ValidationError` | Invalid data — negative amount, past date, empty required field |
| `AppointmentConflictError` | Provider already has an appointment in the requested time slot |
| `NotFoundError` | Entity not found in the database |
| `DuplicateError` | Unique constraint violation — e.g. duplicate email |
| `BusinessRuleError` | Business rule violation — e.g. cancelling an appointment that has a transaction |
| `UnpaidTransactionError` | Operation requires a paid transaction but balance is pending |
| `InactiveOfferingError` | Trying to book or sell an inactive service or product |
| `NoProviderError` | Service requires a provider but none was assigned |
| `InvalidRoleError` | Person does not have the required role |
| `DatabaseError` | Connection or database operation failure |

```python
from gesta import (
    NotFoundError,
    AppointmentConflictError,
    ValidationError,
    GestaError,
)

try:
    with studio.session() as s:
        studio.appointments(s).book(...)

except AppointmentConflictError as e:
    print(f"Schedule conflict: {e}")

except ValidationError as e:
    print(f"Invalid data: {e}")

except NotFoundError as e:
    print(f"{e.entity} not found: {e.identifier}")

except GestaError as e:
    # Catches any Gesta exception
    print(f"Gesta error: {e}")
```

---

## Extending Gesta

Gesta is designed to adapt to any appointment-based business. Create your own extension by subclassing `Gesta`:

```python
from gesta import Gesta
from gesta.core.entities import Role

class HairSalon(Gesta):
    def setup(self):
        with self.session() as s:
            roles = [
                Role(id="role_client",  name="client",  is_recipient=True,  is_provider=False),
                Role(id="role_stylist", name="stylist", is_recipient=False, is_provider=True),
            ]
            for role in roles:
                if not s.get(Role, role.id):
                    s.add(role)

salon = HairSalon(db_url="sqlite:///salon.db")
salon.setup()
```

---

## Using with PostgreSQL

```python
studio = WellnessStudio(
    db_url="postgresql://user:password@localhost/gesta_db"
)
```

Install the PostgreSQL driver:

```bash
pip install psycopg2-binary
```

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Docker

```bash
# Build
docker build -t gesta .

# Run demo
docker run --rm gesta

# Run tests
docker run --rm gesta python -m pytest tests/ -v

# Interactive shell
docker run --rm -it gesta bash
```

---

## Project structure

```
gesta/
├── gesta/
│   ├── __init__.py
│   ├── gesta.py                # Main Gesta class
│   ├── core/
│   │   ├── entities.py         # Person, Role, Offering, Appointment, Transaction, Payment
│   │   ├── database.py         # Engine, session, init_db
│   │   ├── exceptions.py       # Custom exceptions
│   │   └── validators.py       # Reusable validation functions
│   ├── managers/
│   │   ├── calendar.py         # AppointmentManager
│   │   ├── transactions.py     # TransactionManager, PaymentManager
│   │   └── reports.py          # ReportManager
│   └── extensions/
│       └── wellness.py         # WellnessStudio — example extension
├── tests/
├── scripts/
│   └── demo.py
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## License

GNU Affero General Public License v3.0 — see [LICENSE](LICENSE) for details.
