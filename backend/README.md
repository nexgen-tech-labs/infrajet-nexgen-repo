
## **1. Complete Project Structure**

```
ai-ide-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             # Configuration management
│   │   ├── exceptions.py         # Custom exceptions
│   │   ├── dependencies.py       # FastAPI dependencies
│   │   └── logging.py            # Logging configuration
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── endpoints/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── chat.py       # AI chat endpoints
│   │   │   │   ├── files.py      # File operations
│   │   │   │   ├── tools.py      # AI tool execution
│   │   │   │   ├── workspace.py  # Workspace management
│   │   │   │   └── websocket.py  # WebSocket endpoints
│   │   │   └── api.py            # API router
│   │   └── dependencies.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   ├── providers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py       # Base AI provider interface
│   │   │   │   ├── openai.py     # OpenAI provider
│   │   │   │   ├── anthropic.py  # Anthropic provider
│   │   │   │   ├── gemini.py     # Google Gemini provider
│   │   │   │   └── factory.py    # Provider factory
│   │   │   ├── orchestrator.py   # AI task orchestration
│   │   │   ├── tokenizer.py      # Token counting
│   │   │   ├── chunking.py       # Content chunking
│   │   │   └── streaming.py      # Stream processing
│   │   ├── filesystem/
│   │   │   ├── __init__.py
│   │   │   ├── file_manager.py   # File operations
│   │   │   ├── workspace.py      # Workspace management
│   │   │   ├── watcher.py        # File system watcher
│   │   │   └── indexer.py        # Code indexing
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Base tool interface
│   │   │   ├── file_tools.py     # File operations
│   │   │   ├── terminal.py       # Command execution
│   │   │   ├── search.py         # Code search
│   │   │   ├── git_tools.py      # Git operations
│   │   │   └── registry.py       # Tool registry
│   │   ├── websocket/
│   │   │   ├── __init__.py
│   │   │   ├── manager.py        # WebSocket connections
│   │   │   ├── handlers.py       # Real-time handlers
│   │   │   └── events.py         # Event definitions
│   │   └── cache/
│   │       ├── __init__.py
│   │       ├── redis_cache.py    # Redis caching
│   │       └── memory_cache.py   # In-memory caching
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py               # Base models
│   │   ├── chat.py               # Chat models
│   │   ├── files.py              # File models
│   │   ├── workspace.py          # Workspace models
│   │   └── tools.py              # Tool models
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── requests.py           # Request schemas
│   │   ├── responses.py          # Response schemas
│   │   └── websocket.py          # WebSocket schemas
│   └── utils/
│       ├── __init__.py
│       ├── logger.py             # Logging utilities
│       ├── validators.py         # Validation utilities
│       ├── security.py           # Security utilities
│       └── helpers.py            # General helpers
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Test configuration
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_ai_providers.py
│   │   ├── test_tools.py
│   │   └── test_filesystem.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_api_endpoints.py
│   │   └── test_websocket.py
│   └── fixtures/
│       ├── __init__.py
│       └── sample_data.py
├── alembic/                      # Database migrations
│   ├── versions/
│   └── env.py
├── scripts/
│   ├── setup.py                  # Setup script
│   └── deploy.py                 # Deployment script
├── docs/
│   ├── api.md                    # API documentation
│   └── architecture.md           # Architecture docs
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## **2. OOP Best Practices Implementation**

### **A. Abstract Base Classes & Interfaces**

#### **`app/services/ai/providers/base.py`**
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator, Optional
from pydantic import BaseModel, Field
from enum import Enum

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

class AIMessage(BaseModel):
    """Message model for AI conversations"""
    role: MessageRole
    content: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class AIProviderCapabilities(BaseModel):
    """Model capabilities and limits"""
    supports_streaming: bool = True
    supports_tools: bool = True
    supports_images: bool = False
    max_tokens: int = 4000
    context_window: int = 8192
    input_price_per_1k: float = 0.0
    output_price_per_1k: float = 0.0

class AIProvider(ABC):
    """Abstract base class for AI providers - inspired by Kilo Code's ApiHandler"""
    
    def __init__(self, api_key: str, model: str, **kwargs):
        self.api_key = api_key
        self.model = model
        self._validate_credentials()
        self._initialize_client()
    
    @abstractmethod
    def _validate_credentials(self) -> None:
        """Validate API credentials"""
        pass
    
    @abstractmethod
    def _initialize_client(self) -> None:
        """Initialize the AI client"""
        pass
    
    @abstractmethod
    async def create_message(
        self, 
        system_prompt: str, 
        messages: List[AIMessage],
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream AI response - similar to Kilo Code's createMessage"""
        pass
    
    @abstractmethod
    async def count_tokens(self, content: str) -> int:
        """Count tokens in content"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> AIProviderCapabilities:
        """Get model capabilities and limits"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is healthy"""
        pass
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model})"
    
    def __repr__(self) -> str:
        return self.__str__()
```

#### **`app/services/tools/base.py`**
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum

class ToolResult(BaseModel):
    """Result of tool execution"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ToolCategory(str, Enum):
    FILE_OPERATION = "file_operation"
    TERMINAL = "terminal"
    SEARCH = "search"
    GIT = "git"
    SYSTEM = "system"

class BaseTool(ABC):
    """Base tool interface - inspired by Kilo Code's tool system"""
    
    def __init__(self, name: str, description: str, category: ToolCategory):
        self.name = name
        self.description = description
        self.category = category
        self._validate_tool()
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool"""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for AI"""
        pass
    
    @abstractmethod
    def validate_parameters(self, **kwargs) -> bool:
        """Validate tool parameters"""
        pass
    
    def _validate_tool(self) -> None:
        """Validate tool configuration"""
        if not self.name or not self.description:
            raise ValueError("Tool name and description are required")
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"
    
    def __repr__(self) -> str:
        return self.__str__()
```

### **B. Factory Pattern Implementation**

#### **`app/services/ai/providers/factory.py`**
```python
from typing import Dict, Type, Optional
from .base import AIProvider
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .gemini import GeminiProvider
from app.core.config import settings
from app.core.exceptions import ProviderNotSupportedError

class AIProviderFactory:
    """Factory for creating AI providers - inspired by Kilo Code's buildApiHandler"""
    
    _providers: Dict[str, Type[AIProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
    }
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[AIProvider]) -> None:
        """Register a new provider"""
        cls._providers[name] = provider_class
    
    @classmethod
    def create_provider(
        cls, 
        provider_name: str, 
        api_key: str, 
        model: str,
        **kwargs
    ) -> AIProvider:
        """Create a provider instance"""
        if provider_name not in cls._providers:
            raise ProviderNotSupportedError(f"Provider {provider_name} not supported")
        
        provider_class = cls._providers[provider_name]
        return provider_class(api_key=api_key, model=model, **kwargs)
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available providers"""
        return list(cls._providers.keys())
    
    @classmethod
    def get_default_provider(cls) -> AIProvider:
        """Get the default provider"""
        return cls.create_provider(
            provider_name=settings.DEFAULT_AI_PROVIDER,
            api_key=settings.get_api_key(settings.DEFAULT_AI_PROVIDER),
            model=settings.DEFAULT_MODEL
        )
```

### **C. Strategy Pattern for Tools**

#### **`app/services/tools/registry.py`**
```python
from typing import Dict, List, Optional
from .base import BaseTool, ToolCategory
from .file_tools import ReadFileTool, WriteFileTool
from .terminal import ExecuteCommandTool
from .search import SearchCodeTool
from .git_tools import GitStatusTool, GitCommitTool

class ToolRegistry:
    """Registry for managing tools - inspired by Kilo Code's tool system"""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._initialize_default_tools()
    
    def _initialize_default_tools(self) -> None:
        """Initialize default tools"""
        default_tools = [
            ReadFileTool(),
            WriteFileTool(),
            ExecuteCommandTool(),
            SearchCodeTool(),
            GitStatusTool(),
            GitCommitTool(),
        ]
        
        for tool in default_tools:
            self.register_tool(tool)
    
    def register_tool(self, tool: BaseTool) -> None:
        """Register a new tool"""
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def get_tools_by_category(self, category: ToolCategory) -> List[BaseTool]:
        """Get tools by category"""
        return [tool for tool in self._tools.values() if tool.category == category]
    
    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools"""
        return list(self._tools.values())
    
    def get_tool_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get schemas for all tools"""
        return {name: tool.get_schema() for name, tool in self._tools.items()}
    
    async def execute_tool(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name"""
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool {name} not found")
        
        if not tool.validate_parameters(**kwargs):
            return ToolResult(success=False, error="Invalid parameters")
        
        return await tool.execute(**kwargs)
```

### **D. Observer Pattern for WebSocket Events**

#### **`app/services/websocket/events.py`**
```python
from typing import Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum

class EventType(str, Enum):
    AI_RESPONSE = "ai_response"
    TOOL_EXECUTION = "tool_execution"
    FILE_CHANGE = "file_change"
    ERROR = "error"
    HEARTBEAT = "heartbeat"

class WebSocketEvent(BaseModel):
    """Base event model"""
    type: EventType
    data: Dict[str, Any]
    timestamp: float
    session_id: Optional[str] = None

class AIResponseEvent(WebSocketEvent):
    """AI response event"""
    type: EventType = EventType.AI_RESPONSE
    data: Dict[str, Any] = {
        "content": "",
        "is_complete": False,
        "tokens_used": 0
    }

class ToolExecutionEvent(WebSocketEvent):
    """Tool execution event"""
    type: EventType = EventType.TOOL_EXECUTION
    data: Dict[str, Any] = {
        "tool_name": "",
        "result": None,
        "success": False
    }
```

#### **`app/services/websocket/manager.py`**
```python
from typing import Dict, Set, Optional
from fastapi import WebSocket
import asyncio
import json
from .events import WebSocketEvent, EventType
from app.core.logging import get_logger

logger = get_logger(__name__)

class WebSocketManager:
    """WebSocket connection manager - inspired by Kilo Code's real-time communication"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        async with self._lock:
            self.active_connections[session_id] = websocket
            self.connection_metadata[session_id] = {
                "connected_at": asyncio.get_event_loop().time(),
                "last_heartbeat": asyncio.get_event_loop().time()
            }
        
        logger.info(f"WebSocket connected: {session_id}")
    
    async def disconnect(self, session_id: str) -> None:
        """Disconnect a WebSocket connection"""
        async with self._lock:
            if session_id in self.active_connections:
                del self.active_connections[session_id]
            if session_id in self.connection_metadata:
                del self.connection_metadata[session_id]
        
        logger.info(f"WebSocket disconnected: {session_id}")
    
    async def send_event(self, session_id: str, event: WebSocketEvent) -> bool:
        """Send an event to a specific session"""
        if session_id not in self.active_connections:
            return False
        
        try:
            websocket = self.active_connections[session_id]
            await websocket.send_text(event.json())
            return True
        except Exception as e:
            logger.error(f"Failed to send event to {session_id}: {e}")
            await self.disconnect(session_id)
            return False
    
    async def broadcast_event(self, event: WebSocketEvent) -> None:
        """Broadcast an event to all connected sessions"""
        disconnected_sessions = []
        
        for session_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(event.json())
            except Exception as e:
                logger.error(f"Failed to broadcast to {session_id}: {e}")
                disconnected_sessions.append(session_id)
        
        # Clean up disconnected sessions
        for session_id in disconnected_sessions:
            await self.disconnect(session_id)
    
    async def send_heartbeat(self, session_id: str) -> None:
        """Send heartbeat to a session"""
        event = WebSocketEvent(
            type=EventType.HEARTBEAT,
            data={},
            timestamp=asyncio.get_event_loop().time(),
            session_id=session_id
        )
        await self.send_event(session_id, event)
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
    
    def is_connected(self, session_id: str) -> bool:
        """Check if a session is connected"""
        return session_id in self.active_connections
```

### **E. Command Pattern for Tool Execution**

#### **`app/services/tools/command.py`**
```python
from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel
from enum import Enum

class CommandStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class CommandResult(BaseModel):
    """Result of command execution"""
    status: CommandStatus
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = {}

class Command(ABC):
    """Abstract command interface"""
    
    def __init__(self, name: str):
        self.name = name
        self.status = CommandStatus.PENDING
        self.result: Optional[CommandResult] = None
    
    @abstractmethod
    async def execute(self) -> CommandResult:
        """Execute the command"""
        pass
    
    @abstractmethod
    async def undo(self) -> CommandResult:
        """Undo the command"""
        pass
    
    def can_undo(self) -> bool:
        """Check if command can be undone"""
        return False

class CommandInvoker:
    """Command invoker for executing commands"""
    
    def __init__(self):
        self.command_history: List[Command] = []
        self.max_history_size = 100
    
    async def execute_command(self, command: Command) -> CommandResult:
        """Execute a command"""
        try:
            command.status = CommandStatus.EXECUTING
            result = await command.execute()
            command.result = result
            command.status = CommandStatus.COMPLETED
            
            # Add to history
            self.command_history.append(command)
            if len(self.command_history) > self.max_history_size:
                self.command_history.pop(0)
            
            return result
        except Exception as e:
            command.status = CommandStatus.FAILED
            command.result = CommandResult(
                status=CommandStatus.FAILED,
                error=str(e)
            )
            return command.result
    
    async def undo_last_command(self) -> Optional[CommandResult]:
        """Undo the last command"""
        if not self.command_history:
            return None
        
        command = self.command_history.pop()
        if command.can_undo():
            return await command.undo()
        
        return None
    
    def get_history(self) -> List[Command]:
        """Get command history"""
        return self.command_history.copy()
```

### **F. Repository Pattern for Data Access**

#### **`app/services/filesystem/file_manager.py`**
```python
from typing import List, Optional, Dict, Any
from pathlib import Path
import asyncio
import aiofiles
from pydantic import BaseModel
from app.core.exceptions import FileNotFoundError, FileAccessError

class FileInfo(BaseModel):
    """File information model"""
    path: str
    name: str
    size: int
    modified_time: float
    is_directory: bool
    extension: Optional[str] = None

class FileManager:
    """File system manager - inspired by Kilo Code's file operations"""
    
    def __init__(self, root_path: str = "./workspaces"):
        self.root_path = Path(root_path)
        self.root_path.mkdir(exist_ok=True)
        self._file_cache: Dict[str, FileInfo] = {}
        self._cache_lock = asyncio.Lock()
    
    async def read_file(self, file_path: str) -> str:
        """Read file content"""
        full_path = self._get_full_path(file_path)
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not full_path.is_file():
            raise FileAccessError(f"Path is not a file: {file_path}")
        
        try:
            async with aiofiles.open(full_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            return content
        except Exception as e:
            raise FileAccessError(f"Failed to read file {file_path}: {e}")
    
    async def write_file(self, file_path: str, content: str) -> None:
        """Write content to file"""
        full_path = self._get_full_path(file_path)
        
        # Ensure directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            async with aiofiles.open(full_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            # Update cache
            await self._update_file_cache(file_path)
        except Exception as e:
            raise FileAccessError(f"Failed to write file {file_path}: {e}")
    
    async def list_files(self, directory: str = "") -> List[FileInfo]:
        """List files in directory"""
        full_path = self._get_full_path(directory)
        
        if not full_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if not full_path.is_dir():
            raise FileAccessError(f"Path is not a directory: {directory}")
        
        files = []
        try:
            for item in full_path.iterdir():
                file_info = await self._get_file_info(item)
                files.append(file_info)
        except Exception as e:
            raise FileAccessError(f"Failed to list directory {directory}: {e}")
        
        return files
    
    async def get_file_info(self, file_path: str) -> FileInfo:
        """Get file information"""
        full_path = self._get_full_path(file_path)
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        return await self._get_file_info(full_path)
    
    def _get_full_path(self, relative_path: str) -> Path:
        """Get full path from relative path"""
        return self.root_path / relative_path
    
    async def _get_file_info(self, path: Path) -> FileInfo:
        """Get file information from path"""
        stat = path.stat()
        
        return FileInfo(
            path=str(path.relative_to(self.root_path)),
            name=path.name,
            size=stat.st_size,
            modified_time=stat.st_mtime,
            is_directory=path.is_dir(),
            extension=path.suffix if path.is_file() else None
        )
    
    async def _update_file_cache(self, file_path: str) -> None:
        """Update file cache"""
        async with self._cache_lock:
            try:
                file_info = await self.get_file_info(file_path)
                self._file_cache[file_path] = file_info
            except Exception:
                # Remove from cache if file no longer exists
                self._file_cache.pop(file_path, None)
```

## **3. Configuration Management**

#### **`app/core/config.py`**
```python
from pydantic_settings import BaseSettings
from typing import Dict, List, Optional
from functools import lru_cache

class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "AI IDE Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # AI Provider Settings
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DEFAULT_AI_PROVIDER: str = "openai"
    DEFAULT_MODEL: str = "gpt-4"
    
    # File System Settings
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: List[str] = [".py", ".js", ".ts", ".java", ".cpp", ".c", ".h"]
    WORKSPACE_ROOT: str = "./workspaces"
    
    # AI Model Settings
    MAX_TOKENS: int = 4000
    TEMPERATURE: float = 0.7
    MAX_CONCURRENT_REQUESTS: int = 10
    
    # WebSocket Settings
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_MAX_CONNECTIONS: int = 100
    
    # Cache Settings
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL: int = 3600  # 1 hour
    
    # Security Settings
    SECRET_KEY: str = "your-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def get_api_key(self, provider: str) -> str:
        """Get API key for provider"""
        key_map = {
            "openai": self.OPENAI_API_KEY,
            "anthropic": self.ANTHROPIC_API_KEY,
            "gemini": self.GEMINI_API_KEY,
        }
        return key_map.get(provider, "")
    
    def is_provider_available(self, provider: str) -> bool:
        """Check if provider is available"""
        return bool(self.get_api_key(provider))

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

settings = get_settings()
```

## **4. Exception Handling**

#### **`app/core/exceptions.py`**
```python
from typing import Any, Dict, Optional

class AIIDEException(Exception):
    """Base exception for AI IDE"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class ProviderNotSupportedError(AIIDEException):
    """Raised when AI provider is not supported"""
    pass

class FileNotFoundError(AIIDEException):
    """Raised when file is not found"""
    pass

class FileAccessError(AIIDEException):
    """Raised when file access fails"""
    pass

class ToolExecutionError(AIIDEException):
    """Raised when tool execution fails"""
    pass

class WebSocketError(AIIDEException):
    """Raised when WebSocket operation fails"""
    pass

class ValidationError(AIIDEException):
    """Raised when validation fails"""
    pass
```

## **5. Main Application**

#### **`app/main.py`**
```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

from app.core.config import settings
from app.core.exceptions import AIIDEException
from app.api.v1.api import api_router
from app.services.websocket.manager import WebSocketManager
from app.services.ai.providers.factory import AIProviderFactory
from app.services.tools.registry import ToolRegistry

# Global service instances
websocket_manager = WebSocketManager()
tool_registry = ToolRegistry()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize services
    await initialize_services()
    
    yield
    
    # Shutdown
    print("Shutting down application...")
    await cleanup_services()

async def initialize_services():
    """Initialize application services"""
    # Initialize AI providers
    for provider_name in AIProviderFactory.get_available_providers():
        if settings.is_provider_available(provider_name):
            print(f"Initialized AI provider: {provider_name}")
    
    # Initialize tools
    print(f"Initialized {len(tool_registry.get_all_tools())} tools")

async def cleanup_services():
    """Cleanup application services"""
    # Close WebSocket connections
    for session_id in list(websocket_manager.active_connections.keys()):
        await websocket_manager.disconnect(session_id)

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered IDE backend with FastAPI",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Exception handlers
@app.exception_handler(AIIDEException)
async def ai_ide_exception_handler(request: Request, exc: AIIDEException):
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.message,
            "details": exc.details,
            "type": exc.__class__.__name__
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "type": "InternalError"
        }
    )

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "websocket_connections": websocket_manager.get_connection_count(),
        "available_providers": AIProviderFactory.get_available_providers(),
        "registered_tools": len(tool_registry.get_all_tools())
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }
```

## **6. Key OOP Best Practices Implemented**

### **1. Single Responsibility Principle (SRP)**
- Each class has a single, well-defined responsibility
- `AIProvider` handles AI communication
- `ToolRegistry` manages tools
- `WebSocketManager` handles connections

### **2. Open/Closed Principle (OCP)**
- Base classes are open for extension, closed for modification
- New providers can be added without changing existing code
- New tools can be registered without modifying the registry

### **3. Liskov Substitution Principle (LSP)**
- All providers implement the same interface
- All tools follow the same contract
- Subclasses can be used in place of base classes

### **4. Interface Segregation Principle (ISP)**
- Small, focused interfaces
- `AIProvider` has minimal required methods
- `BaseTool` has essential tool methods only

### **5. Dependency Inversion Principle (DIP)**
- High-level modules depend on abstractions
- `AIOrchestrator` depends on `AIProvider` interface
- `ToolRegistry` depends on `BaseTool` interface

### **6. Design Patterns Used**
- **Factory Pattern**: `AIProviderFactory`
- **Strategy Pattern**: Different AI providers
- **Observer Pattern**: WebSocket event system
- **Command Pattern**: Tool execution
- **Repository Pattern**: File system access
- **Singleton Pattern**: Configuration and managers

### **7. Error Handling**
- Custom exception hierarchy
- Graceful error handling with proper HTTP status codes
- Detailed error messages for debugging

### **8. Configuration Management**
- Environment-based configuration
- Type-safe settings with Pydantic
- Cached settings for performance

### **9. Logging and Monitoring**
- Structured logging
- Performance monitoring
- Health check endpoints

### **10. Testing Support**
- Dependency injection for easy mocking
- Clear separation of concerns
- Comprehensive test structure

