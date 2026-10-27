from fastapi import APIRouter

from app.core.errors import NotImplementedYetError
from app.modules.cooks.service import RequireApprovedCook

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.post("/listings", status_code=201)
async def create_listing(cook: RequireApprovedCook) -> None:
    """Stub until listings land (Phase 2). The approved-cook check already runs, so the
    authorization contract is in force: unapproved cooks get 403, approved ones 501."""
    raise NotImplementedYetError("Listings aren't available yet")
