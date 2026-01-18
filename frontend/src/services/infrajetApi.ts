import { supabase } from '@/integrations/supabase/client';
import { ApiError, ErrorType } from '@/lib/ApiError';
import { tokenManager } from '@/lib/TokenManager';
import { loadRuntimeConfig } from '@/config';
import { API_CONFIG } from '@/config/api';

// Base API configuration - will be set after config is loaded
let API_BASE_URL: string;

// Initialize API base URL asynchronously
loadRuntimeConfig().then((config) => {
  API_BASE_URL = config.INFRAJET_API_URL;
}).catch((error) => {
  console.warn('Failed to load runtime config for API URL, using fallback:', error);
  API_BASE_URL = 'http://localhost:8000';
});

// Helper function to get auth token with automatic refresh
export const getAuthToken = async (): Promise<string> => {
    try {
        return await tokenManager.getValidToken();
    } catch (error) {
        if (error instanceof ApiError) {
            throw error;
        }
        throw new ApiError(
            ErrorType.AUTHENTICATION_ERROR,
            'Failed to obtain authentication token',
            401,
            undefined,
            error as Error
        );
    }
};

// Helper function to make authenticated requests with proper error handling
export const makeAuthenticatedRequest = async (
    endpoint: string,
    options: RequestInit = {}
): Promise<Response> => {
    try {
        const token = await getAuthToken();

        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            ...options,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw ApiError.fromResponse(response, errorData);
        }

        return response;
    } catch (error) {
        if (error instanceof ApiError) {
            throw error;
        }

        // Handle network errors
        if (error instanceof TypeError && error.message.includes('fetch')) {
            throw ApiError.fromNetworkError(error as Error);
        }

        throw ApiError.fromUnknownError(error);
    }
};

// Project Types
export interface Project {
    id: string;
    name: string;
    description: string;
    status: string;
    created_at: string;
    updated_at: string;
    azure_folder_path: string;
    github_linked: boolean;
    github_repo_id: number | null;
    github_repo_name: string | null;
    github_installation_id: number | null;
    last_github_sync: string | null;
    file_count?: number;
    total_size?: number;
}

export interface CreateProjectRequest {
    name: string;
    description: string;
    project_id?: string;
    link_to_github?: boolean;
    github_installation_id?: number | null;
}

export interface CreateProjectResponse {
    project: Project;
    is_new: boolean;
    azure_folders_created: string[];
    github_repo_created: boolean;
    github_repo_url: string | null;
    message: string;
}

// Chat Types
export interface ChatMessage {
    id: string;
    project_id: string;
    user_id: string;
    message_content: string;
    message_type: 'user' | 'system' | 'ai';
    timestamp: string;
}

export interface SaveMessageRequest {
    message_content: string;
    message_type: 'user' | 'system' | 'ai';
}

export interface SaveMessageResponse {
    message: ChatMessage;
    success: boolean;
    message_text: string;
}

export interface GetMessagesResponse {
    project_id: string;
    messages: ChatMessage[];
    total_count: number;
    returned_count: number;
    has_more: boolean;
    message_text: string;
}

// Generation Types
export interface Generation {
    generation_id: string;
    query: string;
    scenario: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    created_at: string;
    updated_at: string;
    generation_hash: string;
    error_message: string | null;
    files: GenerationFile[];
    file_count: number;
}

export interface GenerationFile {
    name: string;
    path: string;
    size: number;
    modified_date: string;
    content_type: string;
    content?: string;
}

export interface GetGenerationsResponse {
    project_id: string;
    generations: Generation[];
    total_generations: number;
    message: string;
}

export interface GetGenerationFilesResponse {
    project_id: string;
    generation_id: string;
    files: GenerationFile[];
    file_count: number;
    total_size: number;
    message: string;
}

export interface GetGenerationFileResponse {
    project_id: string;
    generation_id: string;
    file_path: string;
    content: string;
    size: number;
    modified_date: string;
    content_type: string;
    message: string;
}

// Code Generation Types
export interface CodeGenerationRequest {
    query: string;
    scenario: 'NEW_RESOURCE' | 'MODIFY_EXISTING' | 'TROUBLESHOOT';
    project_id?: string;
    project_name?: string;
    save_to_project?: boolean;
    repository_name?: string;
    existing_code?: string;
    target_file_path?: string;
    provider_type?: string;
    temperature?: number;
    max_tokens?: number;
}

export interface CodeGenerationResponse {
    job_id: string;
    status: string;
    message: string;
    project_info?: {
        project_id: string;
        project_name: string;
        project_description: string;
        azure_folder_path: string;
        is_new_project: boolean;
    };
}

export interface JobStatus {
    job_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress?: number;
    message?: string;
}

export interface JobResult {
    job_id: string;
    status: string;
    success: boolean;
    generated_code?: string;
    generated_files?: Record<string, string>;
    project_info?: {
        project_id: string;
        project_name: string;
        project_description: string;
        azure_folder_path: string;
        is_new_project: boolean;
    };
    generated_file_info?: Array<{
        file_path: string;
        azure_path: string;
        file_type: string;
        size_bytes: number;
        content_hash: string;
    }>;
    generation_folder_path?: string;
    azure_paths?: string[];
    github_status?: {
        pushed: boolean;
        repo_url: string;
        commit_sha: string;
        error: string | null;
    };
    diff_content?: string;
    additions?: number;
    deletions?: number;
    changes?: number;
    processing_time_ms?: number;
    error_message?: string | null;
}

// GitHub Types
export interface GitHubInstallation {
    id: number;
    account_login: string;
    account_type: 'User' | 'Organization';
    permissions: Record<string, string>;
    events: string[];
    created_at: string;
    updated_at: string;
}

export interface CreateRepoRequest {
    installation_id: number;
    name: string;
    description?: string;
    private?: boolean;
    owner?: string;
}

export interface PushFilesRequest {
    installation_id: number;
    repo_owner: string;
    repo_name: string;
    files: Record<string, string>;
    commit_message: string;
    branch?: string;
}

export interface LinkProjectToGitHubRequest {
    installation_id: number;
    create_repo?: boolean;
    repo_name?: string;
}


// Project API
export const projectApi = {
    async create(data: CreateProjectRequest): Promise<CreateProjectResponse> {
        const response = await makeAuthenticatedRequest('/api/v1/projects/upsert', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        return response.json();
    },

    async list(params?: {
        include_files?: boolean;
        include_github_info?: boolean;
        status_filter?: string;
    }): Promise<{ projects: Project[]; total_count: number; message: string }> {
        const searchParams = new URLSearchParams();
        if (params?.include_files) searchParams.set('include_files', 'true');
        if (params?.include_github_info) searchParams.set('include_github_info', 'true');
        if (params?.status_filter) searchParams.set('status_filter', params.status_filter);

        const response = await makeAuthenticatedRequest(
            `/api/v1/projects?${searchParams.toString()}`
        );
        return response.json();
    },

    async getById(projectId: string): Promise<Project> {
        const response = await makeAuthenticatedRequest(`/api/v1/projects/${projectId}`);
        return response.json();
    },

    async delete(projectId: string, options?: {
        delete_github_repo?: boolean;
        soft_delete?: boolean;
    }): Promise<void> {
        const searchParams = new URLSearchParams();
        if (options?.delete_github_repo) searchParams.set('delete_github_repo', 'true');
        if (options?.soft_delete) searchParams.set('soft_delete', 'true');

        await makeAuthenticatedRequest(
            `/api/v1/projects/${projectId}?${searchParams.toString()}`,
            { method: 'DELETE' }
        );
    },
};

// Chat API
export const chatApi = {
    async saveMessage(projectId: string, data: SaveMessageRequest): Promise<SaveMessageResponse> {
        const response = await makeAuthenticatedRequest(
            `/api/v1/projects/${projectId}/chat/messages`,
            {
                method: 'POST',
                body: JSON.stringify(data),
            }
        );
        return response.json();
    },

    async getMessages(projectId: string, params?: {
        limit?: number;
        offset?: number;
    }): Promise<GetMessagesResponse> {
        const searchParams = new URLSearchParams();
        if (params?.limit) searchParams.set('limit', params.limit.toString());
        if (params?.offset) searchParams.set('offset', params.offset.toString());

        const response = await makeAuthenticatedRequest(
            `/api/v1/projects/${projectId}/chat/messages?${searchParams.toString()}`
        );
        return response.json();
    },
};

// Generations API
export const generationsApi = {
    async getGenerations(projectId: string): Promise<GetGenerationsResponse> {
        const response = await makeAuthenticatedRequest(
            `/api/v1/projects/${projectId}/generations`
        );
        return response.json();
    },

    async getGenerationFiles(projectId: string, generationId: string, includeContent = false): Promise<GetGenerationFilesResponse> {
        const searchParams = new URLSearchParams();
        if (includeContent) searchParams.set('include_content', 'true');

        const response = await makeAuthenticatedRequest(
            `/api/v1/projects/${projectId}/generations/${generationId}/files?${searchParams.toString()}`
        );
        return response.json();
    },

    async getGenerationFile(projectId: string, generationId: string, filePath: string): Promise<GetGenerationFileResponse> {
        const response = await makeAuthenticatedRequest(
            `/api/v1/projects/${projectId}/generations/${generationId}/files/${encodeURIComponent(filePath)}`
        );
        return response.json();
    },
};

// Code Generation API
export const codeGenerationApi = {
    async generate(data: CodeGenerationRequest): Promise<CodeGenerationResponse> {
        const response = await makeAuthenticatedRequest('/api/v1/code_generation/generate', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        return response.json();
    },

    async getJobStatus(jobId: string): Promise<JobStatus> {
        const response = await makeAuthenticatedRequest(`/api/v1/code_generation/jobs/${jobId}`);
        return response.json();
    },

    async getJobResult(jobId: string): Promise<JobResult> {
        const response = await makeAuthenticatedRequest(`/api/v1/code_generation/jobs/${jobId}/result`);
        return response.json();
    },

    async validateCode(code: string): Promise<any> {
        const response = await makeAuthenticatedRequest('/api/v1/code_generation/validate', {
            method: 'POST',
            body: JSON.stringify({ code }),
        });
        return response.json();
    },

    async generateDiff(oldCode: string, newCode: string): Promise<any> {
        const response = await makeAuthenticatedRequest('/api/v1/code_generation/diff', {
            method: 'POST',
            body: JSON.stringify({ old_code: oldCode, new_code: newCode }),
        });
        return response.json();
    },
};

// GitHub API - Simplified Sync Endpoints
export interface GitHubHealthResponse {
    success: boolean;
    data: {
        service: string;
        status: string;
        checks: Record<string, string>;
        errors: string[];
    };
}

export interface GitHubConnectUrlResponse {
    success: boolean;
    data: {
        authorization_url: string;
        state: string;
        instructions: string;
    };
}

export interface GitHubConnectRequest {
    code: string;
}

export interface GitHubConnectResponse {
    success: boolean;
    data: {
        success: boolean;
        user_info: {
            id: number;
            login: string;
            email: string;
        };
        installations: any[];
        primary_installation_id: number;
        message: string;
    };
    message: string;
}

export interface GitHubStatusResponse {
    success: boolean;
    data: {
        connected: boolean;
        username: string;
        installation_id: number;
        repositories_count: number;
        connected_at: string;
    };
}

export interface GitHubRepository {
    id: number;
    name: string;
    full_name: string;
    description: string | null;
    private: boolean;
    html_url: string;
    clone_url: string;
    created_at: string;
    updated_at: string;
}

export interface GitHubRepositoriesResponse {
    success: boolean;
    data: {
        repositories: GitHubRepository[];
        total_count: number;
        page: number;
        per_page: number;
        has_more: boolean;
    };
    message: string;
}

export interface GitHubSyncRequest {
    files_content: Record<string, string>;
    commit_message: string;
    branch: string;
}

export interface GitHubSyncResponse {
    success: boolean;
    data: {
        success: boolean;
        commit_sha: string;
        files_synced: number;
        repository_url: string;
        commit_url: string;
    };
    message: string;
}

export const githubApi = {
    // Health Check
    async getHealth(): Promise<GitHubHealthResponse> {
        const response = await makeAuthenticatedRequest('/api/v1/github/health');
        return response.json();
    },

    // Setup Guide
    async getSetupGuide(): Promise<any> {
        const response = await makeAuthenticatedRequest('/api/v1/github/setup-guide');
        return response.json();
    },

    // Get Connection URL
    async getConnectUrl(state?: string): Promise<GitHubConnectUrlResponse> {
        const params = state ? `?state=${encodeURIComponent(state)}` : '';
        const response = await makeAuthenticatedRequest(`/api/v1/github/connect-url${params}`);
        return response.json();
    },

    // Connect GitHub
    async connect(data: GitHubConnectRequest): Promise<GitHubConnectResponse> {
        const response = await makeAuthenticatedRequest('/api/v1/github/connect', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        return response.json();
    },

    // Get Connection Status
    async getStatus(): Promise<GitHubStatusResponse> {
        const response = await makeAuthenticatedRequest('/api/v1/github/status');
        return response.json();
    },

    // Get Repositories
    async getRepositories(params?: {
        page?: number;
        per_page?: number;
    }): Promise<GitHubRepositoriesResponse> {
        const searchParams = new URLSearchParams();
        searchParams.set('use_oauth_token', 'true');
        if (params?.page) searchParams.set('page', params.page.toString());
        if (params?.per_page) searchParams.set('per_page', params.per_page.toString());

        const response = await makeAuthenticatedRequest(
            `/api/v1/github/repositories?${searchParams.toString()}`
        );
        return response.json();
    },

    // Sync Files to Repository
    async syncFiles(owner: string, repo: string, data: GitHubSyncRequest): Promise<GitHubSyncResponse> {
        const response = await makeAuthenticatedRequest(`/api/v1/github/repositories/${owner}/${repo}/sync`, {
            method: 'POST',
            body: JSON.stringify(data),
        });
        return response.json();
    },

    // Create Repository
    async createRepository(data: CreateRepoRequest): Promise<any> {
        const response = await makeAuthenticatedRequest('/api/v1/github/repositories', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        return response.json();
    },

    // Check Project GitHub Status
    async getProjectGitHubStatus(projectId: string): Promise<any> {
        const response = await makeAuthenticatedRequest(`/api/v1/github/projects/${projectId}/github-status`);
        return response.json();
    },

    // Link Project to GitHub Repository
    async linkProjectToGitHub(projectId: string, data: LinkProjectToGitHubRequest): Promise<any> {
        const response = await makeAuthenticatedRequest(`/api/v1/github/projects/${projectId}/link-repo`, {
            method: 'POST',
            body: JSON.stringify(data),
        });
        return response.json();
    },

    // Push Project Files to GitHub
    async pushProjectToGitHub(projectId: string, data: { generation_id?: string; commit_message: string }): Promise<any> {
        const response = await makeAuthenticatedRequest(`/api/v1/github/projects/${projectId}/push`, {
            method: 'POST',
            body: JSON.stringify(data),
        });
        return response.json();
    },

    // Auto-sync Generation
    async autoSyncGeneration(generationId: string): Promise<any> {
        const response = await makeAuthenticatedRequest(`/api/v1/github/generations/${generationId}/auto-sync`, {
            method: 'POST',
        });
        return response.json();
    },

    // Disconnect GitHub
    async disconnect(): Promise<any> {
        const response = await makeAuthenticatedRequest('/api/v1/github/disconnect', {
            method: 'DELETE',
        });
        return response.json();
    },
};

// InfraJetChat Class - Following the documentation exactly
export class InfraJetChat {
    private projectId: string;
    private authToken: string;
    private baseUrl: string;
    private wsUrl: string;
    private websocket: WebSocket | null = null;
    private messageHandlers = new Map<string, (data: any) => void>();
    private reconnectAttempts = 5;
    private reconnectCount = 0;

    constructor(projectId: string, authToken: string) {
        this.projectId = projectId;
        this.authToken = authToken;
        this.baseUrl = API_BASE_URL;
        this.wsUrl = this.wsUrl = `${API_BASE_URL.replace('https', 'ws').replace('http', 'ws')}/api/v1/websocket/ws`;;
                

    }

    // Initialize WebSocket connection
    async initWebSocket(): Promise<void> {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            return;
        }

        this.websocket = new WebSocket(`${this.wsUrl}?token=${encodeURIComponent(this.authToken)}`);

        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectCount = 0;
            this.subscribeToProject();
        };

        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            // Implement reconnection logic
            if (this.reconnectCount < this.reconnectAttempts) {
                this.reconnectCount++;
                setTimeout(() => this.initWebSocket(), 5000);
            }
        };
    }

    // Subscribe to project updates
    subscribeToProject(): void {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                action: 'subscribe_project',
                data: { project_id: this.projectId }
            }));
        }
    }

    // Handle WebSocket messages
    handleWebSocketMessage(data: any): void {
        const handler = this.messageHandlers.get(data.type);
        if (handler) {
            handler(data);
        }
    }

    // Register message handlers
    onGenerationStarted(callback: (data: any) => void): void {
        this.messageHandlers.set('generation_started', callback);
    }

    onGenerationProgress(callback: (data: any) => void): void {
        this.messageHandlers.set('generation_progress', callback);
    }

    onGenerationCompleted(callback: (data: any) => void): void {
        this.messageHandlers.set('generation_completed', callback);
    }

    // Send chat message
    async sendMessage(messageContent: string, messageType: 'user' | 'system' | 'ai' = 'user'): Promise<SaveMessageResponse> {
        const response = await fetch(`${this.baseUrl}/api/v1/projects/${this.projectId}/chat/messages`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message_content: messageContent,
                message_type: messageType
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    // Get chat history
    async getChatHistory(limit = 50, offset = 0): Promise<GetMessagesResponse> {
        const response = await fetch(
            `${API_CONFIG.BASE_URL}/api/v1/projects/${this.projectId}/chat/messages?limit=${limit}&offset=${offset}`,
            {
                headers: {
                    'Authorization': `Bearer ${this.authToken}`
                }
            }
        );

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return {
            ...data,
            messages: data.messages || [],
        };
    }

    // Get project generations
    async getGenerations(): Promise<GetGenerationsResponse> {
        const response = await fetch(`${API_CONFIG.BASE_URL}/api/v1/projects/${this.projectId}/generations`, {
            headers: {
                'Authorization': `Bearer ${this.authToken}`
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return {
            ...data,
            generations: data.generations || [],
        };
    }

    // Get generation files
    async getGenerationFiles(generationId: string, includeContent = false): Promise<GetGenerationFilesResponse> {
        const response = await fetch(
            `${API_CONFIG.BASE_URL}/api/v1/projects/${this.projectId}/generations/${generationId}/files?include_content=${includeContent}`,
            {
                headers: {
                    'Authorization': `Bearer ${this.authToken}`
                }
            }
        );

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    // Get specific file
    async getGenerationFile(generationId: string, filePath: string): Promise<GetGenerationFileResponse> {
        const response = await fetch(
            `${API_CONFIG.BASE_URL}/api/v1/projects/${this.projectId}/generations/${generationId}/files/${encodeURIComponent(filePath)}`,
            {
                headers: {
                    'Authorization': `Bearer ${this.authToken}`
                }
            }
        );

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    // Disconnect WebSocket
    disconnect(): void {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
    }
};