from fastapi import APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends
from starlette.middleware.sessions import SessionMiddleware

# Disabled authentication and integration features
# from app.api.v1.auth.routes import router as auth_router
# from app.api.v1.auth.azure_entra_routes import router as azure_entra_router
# from app.api.v1.github.routes import router as github_router

# GitHub integrations (enabled)
from app.api.v1.github.app_routes import router as github_app_router
from app.api.v1.github_simple import router as github_simple_router

# from app.api.v1.users.routes import router as users_router  # Disabled - requires role-based auth
from app.api.v1.embeddings.routes import router as embeddings_router
from app.api.routes.terraform import router as terraform_router
from app.api.v1.code_generation.routes import router as code_generation_router
from app.api.v1.projects.dashboard_routes import router as dashboard_router
from app.api.v1.projects.routes import router as projects_router
from app.api.v1.projects.file_routes import router as project_files_router
from app.api.v1.projects.management_routes import router as project_management_router
from app.api.v1.files.management_routes import router as file_management_router
from app.api.v1.websocket.routes import router as websocket_router
from app.api.v1.websocket.dashboard_routes import router as websocket_dashboard_router
from app.api.v1.chat import router as chat_router
from app.core.settings import get_settings
from app.middleware.auth import verify_firebase_token

settings = get_settings()

api_router = APIRouter()

# Disabled authentication and integration routes
# api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
# api_router.include_router(azure_entra_router, prefix="/auth", tags=["azure-entra-auth"])
# api_router.include_router(github_router, prefix="/github", tags=["github-sync"])

# GitHub integration routes (enabled)
api_router.include_router(github_simple_router, tags=["github-simple"])

# api_router.include_router(users_router, prefix="/users", tags=["users"])  # Disabled - requires role-based auth
api_router.include_router(terraform_router, prefix="/terraform", tags=["terraform"])
api_router.include_router(embeddings_router, prefix="/embeddings", tags=["embeddings"])
api_router.include_router(
    code_generation_router, prefix="/code_generation", tags=["code_generation"]
)
api_router.include_router(dashboard_router, tags=["project-dashboard"])
api_router.include_router(projects_router, tags=["projects"])
api_router.include_router(project_files_router, tags=["project-files"])
api_router.include_router(project_management_router, tags=["project-management"])
api_router.include_router(file_management_router, tags=["file-management"])
api_router.include_router(websocket_router, prefix="/websocket", tags=["websocket"])
api_router.include_router(websocket_dashboard_router, tags=["websocket-dashboard"])
api_router.include_router(chat_router, tags=["project-chat"])

# Import and include autonomous chat router
from app.api.v1.chat import autonomous_router
api_router.include_router(autonomous_router, tags=["autonomous-chat"])

# Import and include enhanced autonomous chat router
from app.api.v1.enhanced_chat import router as enhanced_chat_router
api_router.include_router(enhanced_chat_router, tags=["enhanced-autonomous-chat"])

# Import and include enhanced chat WebSocket routes
from app.api.v1.websocket.enhanced_chat_routes import router as enhanced_chat_ws_router
api_router.include_router(enhanced_chat_ws_router, prefix="/websocket", tags=["enhanced-chat-websocket"])

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=None,
        redoc_url=None,
    )

    # Set up CORS first
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_URL] if settings.FRONTEND_URL else ["http://localhost:8080"],  # Allow frontend origin
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_STR, dependencies=[Depends(verify_firebase_token)])

    @app.get("/")
    async def root():
        return {"message": "Welcome to Infrajet Backend API"}

    return app
