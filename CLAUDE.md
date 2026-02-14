# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

InfraJet is an AI-powered Infrastructure as Code (IaC) generation platform built as a full-stack monorepo. It features autonomous Terraform code generation with RAG-enhanced prompts, real-time collaboration via WebSocket, and seamless GitHub integration.

**Repository Structure:**
- `backend/` - FastAPI + Socket.IO server (Python 3.11+)
- `frontend/` - React + TypeScript SPA with Vite

## Development Commands

### Backend

**Prerequisites:**
- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Redis (Valkey) instance
- Required environment variables in `backend/.env`

**Setup:**
```bash
cd backend

# Install dependencies (using uv or pip)
uv pip install -r requirements.txt
# OR
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Database Migrations:**
```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

**Important:** The backend uses Cloud SQL Connector for PostgreSQL connections in production. Database URL format: `postgresql+asyncpg://user:pass@/dbname?host=/cloudsql/instance-name`

### Frontend

**Prerequisites:**
- Node.js 18+
- Yarn package manager

**Setup:**
```bash
cd frontend

# Install dependencies
yarn install

# Start development server (http://localhost:8080)
yarn dev

# Build for production
yarn build

# Preview production build
yarn preview

# Lint code
yarn lint

# Start production server (with Express)
yarn start
```

**Configuration:**
Frontend configuration is loaded at runtime from `public/config.json`. For development, environment variables in `.env` are used by Vite and transformed into the config.

## Project Architecture

### Backend Architecture

**Main Entry Point:** `backend/main.py`
- Creates FastAPI app with Socket.IO ASGI wrapper
- Startup tasks: database table creation, job queue service, WebSocket manager background tasks
- Uses Firebase authentication globally via middleware

**Service Layer Organization:**

1. **Code Generation Services** (`app/services/code_generation/`)
   - `orchestrator.py` - Coordinates RAG retrieval, LLM generation, validation
   - `generation/pipeline.py` - Autonomous generation pipeline
   - `generation/realtime_pipeline.py` - Real-time generation with progress events
   - `generation/prompt_engineer.py` - Context-aware prompt construction
   - `generation/validator.py` - Terraform/HCL code validation
   - `llm_providers/` - Factory pattern for LLM providers (Claude)
   - `rag/retriever.py` - Vector similarity search for relevant code examples
   - `diff/` - Diff generation and analysis for code changes

2. **Embedding Services**
   - `embedding_service.py` - Anthropic embeddings (1536-dim) with dual embedding support (code + summary)
   - `embedding_orchestrator.py` - Orchestrates embedding operations
   - `llm_summarization_service.py` - LLM-based code summarization for enhanced retrieval

3. **Chat Services** (`app/services/chat/`)
   - `autonomous_chat_service.py` - LLM-driven prompt completeness analysis
   - `terraform_chat_service.py` - Terraform-specific conversations
   - `conversation_context_manager.py` - Multi-turn conversation state management

4. **Sync Services**
   - `sync/concurrency_manager.py` - Manages concurrent sync operations
   - `sync/metadata_sync.py` - File metadata synchronization

5. **GitHub Integration**
   - `github_app_service.py` - GitHub App integration (installation-based)
   - `github_app_oauth_service.py` - Hybrid OAuth + GitHub App
   - `github_sync_orchestrator.py` - Orchestrates repository synchronization
   - `project_github_service.py` - Project-specific GitHub operations

6. **Azure Services** (`app/services/azure/`)
   - `connection.py` - Azure File Share connection pooling
   - `file_operations.py` - File CRUD operations
   - `folder_manager.py` - Folder structure management
   - `retry_manager.py` - Resilient retry logic

7. **Infrastructure Services**
   - `websocket_manager.py` - Socket.IO server with session management, subscriptions, heartbeat
   - `job_queue.py` - Background job queue for async tasks
   - `redis_client.py` - Redis/Valkey client for caching

**Authentication Flow:**
- **Active:** Firebase Authentication via `middleware/auth.py`
- Authentication is enforced globally via `verify_firebase_token()` dependency
- Feature flag in `settings.py`: `FIREBASE_AUTH_ENABLED=True`

**Database Models:**

Key relationships:
- `User` model uses Firebase UID (String) as the primary identifier
- `Project` → User via `user_id` (String - Firebase UID)
- `Project` → `ProjectFile` (one-to-many)
- `Project` → `CodeGeneration` (one-to-many)
- `CodeGeneration` ↔ `ProjectFile` (many-to-many via `GeneratedFile`)
- `Project` → `ConversationThread` → `ProjectChat` (conversation hierarchy)
- `Repository` → `FileEmbedding` (one-to-many, with pgvector embeddings)

**Important:** User IDs are Firebase UIDs (strings) used consistently throughout the application.

**Real-time Communication:**
- Socket.IO server integrated with FastAPI via `socketio.ASGIApp`
- Session management with subscription system (projects, generations, conversations)
- Background tasks: heartbeat loop (30s), cleanup loop (5min timeout for stale connections)
- Events: `generation_progress`, `project_updated`, `clarification_requested`, `conversation_started`
- Client authentication on connect with Firebase token

### Frontend Architecture

**Entry Point:** `src/main.tsx`
- Loads runtime config from `public/config.json`
- Initializes React app with providers

**State Management:**
- Context-based: `AuthContext`, `GitHubContext`, `AdminAuthContext`
- TanStack Query for server state
- Custom hooks in `hooks/` for feature-specific logic

**API Client:** `services/infrajetApi.ts`
- All requests through `makeAuthenticatedRequest()` with auto token injection
- Token refresh via `TokenManager` (auto-refresh before expiry)
- Typed error handling with `ApiError` class
- Modules: `projectApi`, `chatApi`, `generationsApi`, `codeGenerationApi`, `githubApi`

**Real-time Integration:** `hooks/useWebSocket.ts`
- WebSocket connection to backend with auto-reconnect
- Event-based message handling
- Subscription management for real-time updates

**Component Organization:**
- `components/ui/` - Radix UI + shadcn/ui components (43 components)
- `components/projects/` - Project management components
- `components/chat/` - Chat interfaces (generic, Terraform-specific, autonomous)
- `components/github/` - GitHub integration UI
- `components/admin/` - Admin dashboard components
- `pages/` - Route-level page components

**Routing:**
- React Router v6 with protected routes via `<AuthGuard>` and `<AdminAuthGuard>`
- OAuth callback handlers: `GitHubCallback.tsx`, `GitHubOAuthCallback.tsx`

## Key Patterns and Conventions

### Backend Patterns

1. **Service Layer Pattern:** All business logic in service classes under `app/services/`
2. **Factory Pattern:** `ProviderFactory` for LLM providers (extensible to OpenAI, Gemini, etc.)
3. **Orchestrator Pattern:** High-level orchestrators coordinate multiple services
4. **Async/Await:** Fully asynchronous with `asyncio`, use `AsyncSession` for database
5. **Dependency Injection:** FastAPI's `Depends()` for service and database injection
6. **Event-Driven:** Socket.IO broadcasts for real-time updates
7. **RAG Pattern:** Retrieval-Augmented Generation with pgvector similarity search

### Code Organization Rules

**Backend:**
- Models in `app/models/` using SQLAlchemy declarative base
- API routes in `app/api/v1/` organized by feature
- Pydantic schemas for request/response validation
- Configuration in `app/core/settings.py` using `pydantic-settings`
- All I/O operations must be async (use `aiofiles`, `asyncpg`, `aiohttp`)

**Frontend:**
- Components use TypeScript with explicit types
- API calls via centralized client in `services/infrajetApi.ts`
- Context providers in `contexts/`
- Custom hooks in `hooks/` for reusable logic
- UI components from `components/ui/` (do not modify directly - generated by shadcn)

### Database Conventions

**Naming:**
- Tables: snake_case (e.g., `project_files`, `code_generations`)
- Columns: snake_case
- Foreign keys: `{table_name}_id` (e.g., `project_id`, `user_id`)

**Migrations:**
- Always use Alembic for schema changes
- Descriptive migration names: `add_github_sync_enhancements.py`
- Data migrations in `alembic/data_migrations/` (separate from schema migrations)
- pgvector operations require manual SQL in migrations (not auto-generated)

**User ID Strategy:**
- User model uses Firebase UID (String) as the primary identifier
- Projects and generations use `user_id` as String (Firebase UID format)
- Firebase UIDs are used consistently across frontend and backend

### Error Handling

**Backend:**
- Custom exceptions in `app/core/exceptions.py` (not currently implemented - use standard HTTP exceptions)
- HTTP exception handlers in `main.py`
- Structured logging with `loguru`
- Health check endpoint at `/health`

**Frontend:**
- `ApiError` class with typed error categories
- Error boundaries for component-level error handling
- Toast notifications via `sonner` for user-facing errors

## External Service Integration

### Required Services

1. **PostgreSQL with pgvector:**
   - Extensions: `pgvector`, `uuid-ossp`
   - Cloud SQL Connector for GCP deployments
   - Connection pooling via AsyncPG

2. **Redis (Valkey):**
   - Job queue and caching
   - Connection via `redis==6.4.0`

3. **Azure File Share:**
   - Project file storage: `projects/{project_id}/{generation_hash}/files`
   - Connection pooling and retry logic

4. **Anthropic API:**
   - Claude for code generation
   - Embeddings: `claude-3-haiku-20240307` (1536 dimensions)
   - Configured via `ANTHROPIC_API_KEY`

5. **Firebase:**
   - Authentication (ACTIVE)
   - Token verification in middleware
   - Frontend and backend authentication
   - Configured via `FIREBASE_PROJECT_ID`

6. **GitHub:**
   - GitHub App integration (installation-based)
   - OAuth flow for user authentication
   - Requires: `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`

## Common Development Tasks

### Adding a New API Endpoint

1. Create route in `backend/app/api/v1/{feature}/routes.py`
2. Add Pydantic schemas for request/response validation
3. Implement business logic in service class under `app/services/`
4. Register router in `backend/app/api/v1/api.py`
5. Update frontend API client in `frontend/src/services/infrajetApi.ts`
6. Add TypeScript types for request/response

### Adding Database Tables

1. Define model in `backend/app/models/{feature}.py` using SQLAlchemy
2. Import model in `backend/app/models/__init__.py`
3. Run: `alembic revision --autogenerate -m "add {feature} table"`
4. Review and adjust generated migration
5. Apply: `alembic upgrade head`

### Adding Real-time Features

1. Define event in `backend/app/services/websocket_manager.py`
2. Emit event from service: `await websocket_manager.broadcast_to_project(project_id, event_data)`
3. Add event handler in `frontend/src/hooks/useWebSocket.ts`
4. Update UI component to handle event

### Working with Embeddings

1. Parse files with tree-sitter: `app/services/tree_sitter/terraform_parser.py`
2. Chunk content (400 tokens, 60 overlap): `app/services/embedding_service.py`
3. Generate embeddings: `EmbeddingService.embed_file()`
4. Store in `FileEmbedding` table with pgvector
5. Retrieve via similarity search: `RAGRetriever.retrieve_similar_code()`

## Important Notes

### Authentication

- **Active authentication:** Firebase (backend middleware + frontend SDK)
- All API routes require Firebase authentication unless explicitly excluded
- Frontend and backend both use Firebase SDK for authentication
- Firebase tokens are verified via middleware on all protected routes

### User ID Strategy

- User model uses Firebase UID (String) as the primary identifier
- Projects and generations use `user_id` as String (Firebase UID format)
- Firebase UIDs are used consistently across frontend and backend

### GitHub Integration

Two integration methods available:
1. **GitHub App (Recommended):** Installation-based, requires GitHub App setup
2. **OAuth:** User-level access tokens, simpler but less secure

Both store credentials in `GitHubConnection` table with encryption.

### Environment Variables

**Backend Critical:**
- `DATABASE_URL` - PostgreSQL connection string (Cloud SQL format)
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
- `ANTHROPIC_API_KEY` - Required for code generation and embeddings
- `FIREBASE_PROJECT_ID` - Required for authentication
- `FIREBASE_WEB_API_KEY` - Firebase web API key
- `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`

**Frontend Critical:**
- Runtime config in `public/config.json` (generated from env vars in build)
- `VITE_API_URL`, `VITE_WS_URL`
- `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`

### Code Generation Flow

1. User enters prompt in chat interface
2. Autonomous chat service analyzes prompt completeness
3. If incomplete, request clarification via WebSocket
4. RAG retriever finds similar code from embeddings
5. Prompt engineer constructs context-aware prompt
6. Claude generates Terraform code
7. Validator checks syntax and structure
8. Error corrector fixes issues if validation fails
9. Files stored in Azure File Share
10. Metadata stored in PostgreSQL
11. Real-time progress updates via Socket.IO
12. Optional: Auto-sync to GitHub

### Performance Considerations

- Database queries use async sessions with connection pooling
- Redis caching for frequently accessed data
- Socket.IO connection limits and cleanup (stale connections after 5min)
- Job queue for long-running tasks (embedding generation, GitHub sync)
- Azure retry manager for transient failures (exponential backoff)

### Testing

**Note:** Test suite is not currently implemented. When adding tests:
- Backend: Use `pytest` with `pytest-asyncio` for async tests
- Frontend: Use Vitest (configured but no tests present)
- Mock external services (Anthropic, GitHub, Azure, Firebase)

## Project-Specific Gotchas

1. **Socket.IO ASGI Wrapper:** The FastAPI app is wrapped with `socketio.ASGIApp`, so use `fastapi_app` for event handlers, not `app`.

2. **pgvector Migrations:** Vector columns require manual SQL in migrations (`op.execute()`), not auto-generated by Alembic.

3. **Dual Embeddings:** Files have both code embeddings and summary embeddings for enhanced retrieval.

4. **GitHub App Private Key:** Must be stored as multi-line string, convert to single-line for env vars or use file path.

5. **Cloud SQL Connector:** Unix socket connection format for PostgreSQL in GCP: `?host=/cloudsql/instance-name`

6. **Frontend Config:** Changes to API URLs require rebuilding `config.json`, not just `.env` changes.

7. **WebSocket Authentication:** Client must send Firebase token in `auth` parameter on connect, not in headers.

8. **Alembic Data Migrations:** Separate directory `alembic/data_migrations/` for data-only migrations (not run by `alembic upgrade`).
