import uvicorn
from fastapi import FastAPI
import socketio
from logconfig.logger import get_logger, get_context_filter
from app.api.v1.api import create_app
from app.core.config import get_settings
from app.db.session import engine, create_tables
from app.services.job_queue import job_queue_service
from app.services.websocket_manager import websocket_manager

# Initialize logger
logger = get_logger()
context_filter = get_context_filter()
settings = get_settings()

# Create FastAPI app
fastapi_app = create_app()  # CORS updated, autonomous router included, provider factory and API key fixed, enum updated with uppercase, autonomous endpoints added

# Mount Socket.IO ASGI app
app = socketio.ASGIApp(websocket_manager.sio, fastapi_app)

# Add startup and shutdown handlers to the underlying FastAPI app
# since ASGIApp doesn't support on_event decorators
@fastapi_app.on_event("startup")
async def startup_event():
    # Set request context
    context_filter.set_context(request_id="startup", user_id="system")

    # Create database tables
    await create_tables()
    logger.info("Application startup: Database tables created successfully")

    # Start job queue service
    await job_queue_service.start()
    logger.info("Application startup: Job queue service started")

    # Start WebSocket manager background tasks
    await websocket_manager.start_background_tasks()
    logger.info("Application startup: WebSocket manager background tasks started")

    # Create first superuser if it doesn't exist
    # from app.services.auth import AuthService
    # from sqlalchemy.ext.asyncio import AsyncSession
    # from app.db.session import get_db

    # async for db in get_db():
    #     user = await AuthService.get_user_by_email(db, settings.FIRST_SUPERUSER_EMAIL)
    #     if not user:
    #         user_in = {
    #             "email": settings.FIRST_SUPERUSER_EMAIL,
    #             "password": settings.FIRST_SUPERUSER_PASSWORD,
    #             "full_name": "Admin",
    #             "is_active": True,
    #             "role": "superuser"
    #         }
    #         await AuthService.create_user(db, user_in)
    #         logger.info("Created initial superuser")


@fastapi_app.on_event("shutdown")
async def shutdown_event():
    # Stop background services
    await job_queue_service.stop()
    await websocket_manager.stop_background_tasks()
    logger.info("Application shutdown: Background services stopped")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
