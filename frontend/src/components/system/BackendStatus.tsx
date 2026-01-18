import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from '@/components/ui/dialog';
import {
    CheckCircle,
    XCircle,
    Clock,
    RefreshCw,
    Server,
    Database,
    Wifi,
    AlertTriangle,
    Info
} from 'lucide-react';
import { ApiTester, ApiTestResult } from '@/utils/apiTest';
import { useToast } from '@/hooks/use-toast';

interface BackendStatusProps {
    className?: string;
}

interface ConnectionStatus {
    backend: 'connected' | 'disconnected' | 'testing';
    database: 'connected' | 'disconnected' | 'unknown';
    github: 'connected' | 'disconnected' | 'unknown';
    lastChecked: Date | null;
}

const API_BASE_URL = window.__RUNTIME_CONFIG__?.INFRAJET_API_URL;

const BackendStatus: React.FC<BackendStatusProps> = ({ className }) => {
    const [status, setStatus] = useState<ConnectionStatus>({
        backend: 'testing',
        database: 'unknown',
        github: 'unknown',
        lastChecked: null,
    });
    const [testResults, setTestResults] = useState<ApiTestResult[]>([]);
    const [isTestingOpen, setIsTestingOpen] = useState(false);
    const [testProgress, setTestProgress] = useState(0);
    const [isTesting, setIsTesting] = useState(false);

    const { toast } = useToast();

    const checkBackendStatus = async () => {
        setIsTesting(true);
        setTestProgress(0);

        try {
            const tester = new ApiTester();

            // Test basic connectivity
            setTestProgress(25);
            const projectsTest = await tester.testProjectsEndpoint();

            setTestProgress(50);
            const codeGenTest = await tester.testCodeGeneration({
                query: 'Test connectivity',
                scenario: 'NEW_RESOURCE',
                provider_type: 'aws',
            });

            setTestProgress(75);

            // Get all results
            const results = tester.getResults();
            setTestResults(results);

            setTestProgress(100);

            // Determine status based on results
            const backendConnected = results.some(r => r.success);
            const allPassed = results.every(r => r.success);

            setStatus({
                backend: backendConnected ? 'connected' : 'disconnected',
                database: allPassed ? 'connected' : 'unknown',
                github: 'unknown', // Would need GitHub token to test
                lastChecked: new Date(),
            });

            if (backendConnected) {
                toast({
                    title: "Backend connection successful",
                    description: `${results.filter(r => r.success).length}/${results.length} endpoints working`,
                });
            } else {
                toast({
                    title: "Backend connection failed",
                    description: "Unable to connect to the InfraJet API",
                    variant: "destructive",
                });
            }

        } catch (error) {
            setStatus(prev => ({
                ...prev,
                backend: 'disconnected',
                lastChecked: new Date(),
            }));

            toast({
                title: "Connection test failed",
                description: error instanceof Error ? error.message : 'Unknown error',
                variant: "destructive",
            });
        } finally {
            setIsTesting(false);
            setTestProgress(0);
        }
    };

    // Auto-check on mount
    useEffect(() => {
        checkBackendStatus();
    }, []);

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'connected':
                return <CheckCircle className="h-4 w-4 text-green-600" />;
            case 'disconnected':
                return <XCircle className="h-4 w-4 text-red-600" />;
            case 'testing':
                return <RefreshCw className="h-4 w-4 text-blue-600 animate-spin" />;
            default:
                return <Clock className="h-4 w-4 text-gray-400" />;
        }
    };

    const getStatusBadge = (status: string) => {
        switch (status) {
            case 'connected':
                return <Badge variant="default" className="bg-green-600">Connected</Badge>;
            case 'disconnected':
                return <Badge variant="destructive">Disconnected</Badge>;
            case 'testing':
                return <Badge variant="secondary">Testing...</Badge>;
            default:
                return <Badge variant="outline">Unknown</Badge>;
        }
    };

    return (
        <Card className={className}>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <Server className="h-5 w-5" />
                            Backend Status
                        </CardTitle>
                        <CardDescription>
                            InfraJet API connection and service status
                        </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            onClick={checkBackendStatus}
                            disabled={isTesting}
                            variant="outline"
                            size="sm"
                        >
                            {isTesting ? (
                                <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                            ) : (
                                <RefreshCw className="h-4 w-4 mr-2" />
                            )}
                            Test Connection
                        </Button>

                        <Dialog open={isTestingOpen} onOpenChange={setIsTestingOpen}>
                            <DialogTrigger asChild>
                                <Button variant="ghost" size="sm">
                                    <Info className="h-4 w-4" />
                                </Button>
                            </DialogTrigger>
                            <DialogContent className="max-w-2xl">
                                <DialogHeader>
                                    <DialogTitle>API Integration Test Results</DialogTitle>
                                    <DialogDescription>
                                        Detailed results from backend connectivity tests
                                    </DialogDescription>
                                </DialogHeader>
                                <div className="space-y-4">
                                    {testResults.length === 0 ? (
                                        <p className="text-muted-foreground">No test results available. Run a connection test first.</p>
                                    ) : (
                                        <div className="space-y-3">
                                            {testResults.map((result, index) => (
                                                <div key={index} className="flex items-start gap-3 p-3 border rounded-lg">
                                                    {getStatusIcon(result.success ? 'connected' : 'disconnected')}
                                                    <div className="flex-1">
                                                        <p className="font-medium">{result.endpoint}</p>
                                                        {result.success ? (
                                                            <p className="text-sm text-green-600">✓ Success</p>
                                                        ) : (
                                                            <p className="text-sm text-red-600">✗ {result.error}</p>
                                                        )}
                                                        {result.data && (
                                                            <pre className="text-xs text-muted-foreground mt-1 bg-muted p-2 rounded">
                                                                {JSON.stringify(result.data, null, 2)}
                                                            </pre>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </DialogContent>
                        </Dialog>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    {/* Progress bar during testing */}
                    {isTesting && (
                        <div className="space-y-2">
                            <div className="flex items-center justify-between text-sm">
                                <span>Testing connection...</span>
                                <span>{testProgress}%</span>
                            </div>
                            <Progress value={testProgress} className="w-full" />
                        </div>
                    )}

                    {/* Service Status */}
                    <div className="grid gap-3">
                        <div className="flex items-center justify-between p-3 border rounded-lg">
                            <div className="flex items-center gap-3">
                                <Server className="h-5 w-5 text-muted-foreground" />
                                <div>
                                    <p className="font-medium">InfraJet API</p>
                                    <p className="text-sm text-muted-foreground">
                                        {API_BASE_URL}
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                {getStatusIcon(status.backend)}
                                {getStatusBadge(status.backend)}
                            </div>
                        </div>

                        <div className="flex items-center justify-between p-3 border rounded-lg">
                            <div className="flex items-center gap-3">
                                <Database className="h-5 w-5 text-muted-foreground" />
                                <div>
                                    <p className="font-medium">Database</p>
                                    <p className="text-sm text-muted-foreground">Project data storage</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                {getStatusIcon(status.database)}
                                {getStatusBadge(status.database)}
                            </div>
                        </div>

                        <div className="flex items-center justify-between p-3 border rounded-lg">
                            <div className="flex items-center gap-3">
                                <Wifi className="h-5 w-5 text-muted-foreground" />
                                <div>
                                    <p className="font-medium">GitHub Integration</p>
                                    <p className="text-sm text-muted-foreground">Repository synchronization</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                {getStatusIcon(status.github)}
                                {getStatusBadge(status.github)}
                            </div>
                        </div>
                    </div>

                    {/* Last Checked */}
                    {status.lastChecked && (
                        <div className="text-sm text-muted-foreground text-center pt-2 border-t">
                            Last checked: {status.lastChecked.toLocaleString()}
                        </div>
                    )}

                    {/* Connection Issues Warning */}
                    {status.backend === 'disconnected' && (
                        <div className="flex items-start gap-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
                            <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
                            <div className="text-sm">
                                <p className="font-medium text-yellow-800 dark:text-yellow-200">
                                    Backend Connection Issue
                                </p>
                                <p className="text-yellow-700 dark:text-yellow-300 mt-1">
                                    Make sure your InfraJet FastAPI backend is running on{' '}
                                    <code className="bg-yellow-100 dark:bg-yellow-800 px-1 rounded">
                                        {API_BASE_URL}  {/*Fetches backend-env in runtime*/}
                                    </code>
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
};

export default BackendStatus;