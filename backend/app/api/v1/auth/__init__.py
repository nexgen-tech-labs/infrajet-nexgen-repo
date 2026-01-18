from .routes import router as auth_router
from .azure_entra_routes import router as azure_entra_router

__all__ = ["auth_router", "azure_entra_router"]
