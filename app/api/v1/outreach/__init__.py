from fastapi import APIRouter

from .equity import router as equity_router
from .postcards import router as postcards_router
from .open_house import router as open_house_router
from .referrals import router as referrals_router
from .reviews import router as reviews_router

router = APIRouter(prefix="/outreach")
router.include_router(equity_router)
router.include_router(postcards_router)
router.include_router(open_house_router)
router.include_router(referrals_router)
router.include_router(reviews_router)
