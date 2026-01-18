// API Integration Test Utility
// This file helps test the backend integration without sample data

import { projectApi, chatApi, codeGenerationApi, githubApi } from '@/services/infrajetApi';

export interface ApiTestResult {
    endpoint: string;
    success: boolean;
    error?: string;
    data?: any;
}

export class ApiTester {
    private results: ApiTestResult[] = [];

    async testProjectsEndpoint(): Promise<ApiTestResult> {
        try {
            const data = await projectApi.list({
                include_files: true,
                include_github_info: true,
            });

            const result: ApiTestResult = {
                endpoint: 'GET /api/v1/projects',
                success: true,
                data: {
                    projectCount: (data.projects || []).length,
                    totalCount: data.total_count,
                    hasFiles: (data.projects || []).some(p => p.file_count !== undefined),
                    hasGitHubInfo: (data.projects || []).some(p => p.github_linked),
                }
            };

            this.results.push(result);
            return result;
        } catch (error) {
            const result: ApiTestResult = {
                endpoint: 'GET /api/v1/projects',
                success: false,
                error: error instanceof Error ? error.message : 'Unknown error'
            };

            this.results.push(result);
            return result;
        }
    }

    async testProjectCreation(projectData: {
        name: string;
        description: string;
        link_to_github?: boolean;
    }): Promise<ApiTestResult> {
        try {
            const data = await projectApi.create(projectData);

            const result: ApiTestResult = {
                endpoint: 'POST /api/v1/projects/upsert',
                success: true,
                data: {
                    projectId: data.project.id,
                    projectName: data.project.name,
                    isNew: data.is_new,
                    azureFoldersCreated: data.azure_folders_created.length,
                    githubRepoCreated: data.github_repo_created,
                }
            };

            this.results.push(result);
            return result;
        } catch (error) {
            const result: ApiTestResult = {
                endpoint: 'POST /api/v1/projects/upsert',
                success: false,
                error: error instanceof Error ? error.message : 'Unknown error'
            };

            this.results.push(result);
            return result;
        }
    }

    async testChatEndpoint(projectId: string): Promise<ApiTestResult> {
        try {
            const data = await chatApi.getMessages(projectId);

            const result: ApiTestResult = {
                endpoint: `GET /api/v1/projects/${projectId}/chat/messages`,
                success: true,
                data: {
                    messageCount: data.messages.length,
                    totalCount: data.total_count,
                    hasMore: data.has_more,
                }
            };

            this.results.push(result);
            return result;
        } catch (error) {
            const result: ApiTestResult = {
                endpoint: `GET /api/v1/projects/${projectId}/chat/messages`,
                success: false,
                error: error instanceof Error ? error.message : 'Unknown error'
            };

            this.results.push(result);
            return result;
        }
    }

    async testCodeGeneration(request: {
        query: string;
        scenario: 'NEW_RESOURCE' | 'MODIFY_EXISTING' | 'TROUBLESHOOT';
        provider_type?: string;
    }): Promise<ApiTestResult> {
        try {
            const data = await codeGenerationApi.generate(request);

            const result: ApiTestResult = {
                endpoint: 'POST /api/v1/code_generation/generate',
                success: true,
                data: {
                    jobId: data.job_id,
                    status: data.status,
                    message: data.message,
                    hasProjectInfo: !!data.project_info,
                }
            };

            this.results.push(result);
            return result;
        } catch (error) {
            const result: ApiTestResult = {
                endpoint: 'POST /api/v1/code_generation/generate',
                success: false,
                error: error instanceof Error ? error.message : 'Unknown error'
            };

            this.results.push(result);
            return result;
        }
    }

    async testGitHubInstallations(githubToken: string): Promise<ApiTestResult> {
        try {
            const data = await githubApi.getInstallations(githubToken);

            const result: ApiTestResult = {
                endpoint: 'GET /api/v1/github/app/installations',
                success: true,
                data: {
                    installationCount: data.length,
                    installations: data.map(inst => ({
                        id: inst.id,
                        accountLogin: inst.account_login,
                        accountType: inst.account_type,
                    })),
                }
            };

            this.results.push(result);
            return result;
        } catch (error) {
            const result: ApiTestResult = {
                endpoint: 'GET /api/v1/github/app/installations',
                success: false,
                error: error instanceof Error ? error.message : 'Unknown error'
            };

            this.results.push(result);
            return result;
        }
    }

    async runAllTests(githubToken?: string): Promise<ApiTestResult[]> {
        console.log('🧪 Starting API Integration Tests...');

        // Test 1: List Projects
        console.log('📋 Testing project listing...');
        await this.testProjectsEndpoint();

        // Test 2: Create Project (optional - only if you want to test creation)
        // console.log('➕ Testing project creation...');
        // await this.testProjectCreation({
        //   name: 'Test Project',
        //   description: 'API Integration Test Project',
        // });

        // Test 3: Chat (requires existing project)
        // console.log('💬 Testing chat endpoint...');
        // await this.testChatEndpoint('existing-project-id');

        // Test 4: Code Generation
        console.log('🤖 Testing code generation...');
        await this.testCodeGeneration({
            query: 'Create a simple S3 bucket',
            scenario: 'NEW_RESOURCE',
            provider_type: 'aws',
        });

        // Test 5: GitHub Installations (requires GitHub token)
        if (githubToken) {
            console.log('🐙 Testing GitHub installations...');
            await this.testGitHubInstallations(githubToken);
        }

        console.log('✅ API Integration Tests Complete');
        return this.results;
    }

    getResults(): ApiTestResult[] {
        return this.results;
    }

    printResults(): void {
        console.log('\n📊 API Integration Test Results:');
        console.log('================================');

        this.results.forEach((result, index) => {
            const status = result.success ? '✅' : '❌';
            console.log(`${index + 1}. ${status} ${result.endpoint}`);

            if (result.success && result.data) {
                console.log(`   Data:`, result.data);
            } else if (!result.success && result.error) {
                console.log(`   Error: ${result.error}`);
            }
            console.log('');
        });

        const successCount = this.results.filter(r => r.success).length;
        const totalCount = this.results.length;

        console.log(`Summary: ${successCount}/${totalCount} tests passed`);

        if (successCount === totalCount) {
            console.log('🎉 All API endpoints are working correctly!');
        } else {
            console.log('⚠️  Some API endpoints need attention.');
        }
    }
}

// Utility function to test API connectivity
export const testApiConnectivity = async (githubToken?: string): Promise<boolean> => {
    const tester = new ApiTester();
    const results = await tester.runAllTests(githubToken);
    tester.printResults();

    return results.every(result => result.success);
};

// Export for use in components
export default ApiTester;