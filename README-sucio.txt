Clases principales:
1. Person          → cualquier participante (cliente, colaborador, etc.)
2. Role            → qué papel juega una Person en el negocio
3. Offering        → abstracta: lo que el negocio ofrece
   ├── Service     → oferta que requiere agenda y proveedor
   └── Product     → oferta física con inventario
4. Appointment     → reserva futura de un Service
5. Transaction     → hecho consumado: qué se entregó, a quién, cuándo
6. Payment         → movimiento de dinero ligado a una Transaction
7. Gesta           → clase principal que orquesta todo







gesta/                          ← repo raíz
├── gesta/                      ← paquete instalable
│   ├── __init__.py             ← expone la API pública: from gesta import Gesta
│   ├── gesta.py                ← clase principal, orquesta todo
│   │
│   ├── core/
│   │   ├── __init__.py         ← expone: from gesta.core import Person, Service, ...
│   │   ├── entities.py          define las clases del dominio del negocio
│   │   ├── database.py          maneja la conexión a la base de datos
│   │   ├── exceptions.py        jerarquia de errores
│   │   └── validators.py        validan la info antes de escribir a la base de datos
│   │
│   ├── managers/
│   │   ├── __init__.py         ← expone: from gesta.managers import AppointmentManager, ...
│   │   ├── calendar.py          gestor de citas
│   │   ├── transactions.py      gestor de transacciones y pagos
│   │   └── reports.py           gestor de reportes y resúmenes financieros
│   │
│   └── extensions/
│       ├── __init__.py         ← vacío por ahora
│       └── wellness.py          extension para negocios de bienestar integral
│        ...
│
├── tests/                      ← pruebas unitarias (lo agregamos desde ahora)
│   ├── __init__.py
│   ├── test_entities.py
│   ├── test_calendar.py
│   └── test_transactions.py
│
├── .gitignore
├── .python_version
├── LICENSE
├── main.py                     ← sandbox de pruebas durante desarrollo
├── pyproject.toml
└── README.md





core:
entities.pyDefine las clases del dominio del negocio.


