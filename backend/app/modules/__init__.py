"""Bounded contexts. Each module owns its tables, router and services, and talks to other
modules through their service functions or outbox events, not their tables.

Allowed dependencies are enforced by tests/unit/test_module_boundaries.py."""

from fastapi import APIRouter

from app.modules.admin import models as _admin_models  # noqa: F401
from app.modules.admin.router import router as admin_router
from app.modules.catalog import models as _catalog_models  # noqa: F401
from app.modules.catalog.router import router as catalog_router
from app.modules.cooks import models as _cooks_models  # noqa: F401
from app.modules.cooks.router import router as cooks_router
from app.modules.identity import models as _identity_models  # noqa: F401
from app.modules.identity.router import router as identity_router
from app.modules.inventory import models as _inventory_models  # noqa: F401
from app.modules.inventory.router import router as inventory_router
from app.modules.logistics import models as _logistics_models  # noqa: F401
from app.modules.logistics.router import router as logistics_router
from app.modules.notifications import models as _notifications_models  # noqa: F401
from app.modules.notifications.router import router as notifications_router
from app.modules.orders import models as _orders_models  # noqa: F401
from app.modules.orders.router import router as orders_router
from app.modules.payments import models as _payments_models  # noqa: F401
from app.modules.payments.router import router as payments_router

ROUTERS: list[APIRouter] = [
    identity_router,
    cooks_router,
    catalog_router,
    inventory_router,
    orders_router,
    payments_router,
    logistics_router,
    notifications_router,
    admin_router,
]
