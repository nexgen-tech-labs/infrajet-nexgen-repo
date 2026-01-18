import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
    Form,
    FormControl,
    FormDescription,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from '@/components/ui/form';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import {
    Code,
    Play,
    CheckCircle,
    XCircle,
    Clock,
    FileText,
    Github,
    Download,
    Copy,
    Loader2
} from 'lucide-react';
import { useCodeGenerationFlow } from '@/hooks/useCodeGeneration';
import { CodeGenerationRequest } from '@/services/infrajetApi';
import { useToast } from '@/hooks/use-toast';

const formSchema = z.object({
    query: z.string().min(10, 'Query must be at least 10 characters'),
    scenario: z.enum(['NEW_RESOURCE', 'MODIFY_EXISTING', 'TROUBLESHOOT']),
    project_id: z.string().optional(),
    save_to_project: z.boolean().default(true),
    provider_type: z.string().default('aws'),
    target_file_path: z.string().optional(),
    existing_code: z.string().optional(),
    temperature: z.number().min(0).max(1).default(0.7),
    max_tokens: z.number().min(100).max(4000).default(2048),
});

type FormData = z.infer<typeof formSchema>;

interface CodeGeneratorProps {
    projectId?: string;
    className?: string;
}

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
    const getStatusConfig = (status: string) => {
        switch (status) {
            case 'pending':
                return { variant: 'secondary' as const, icon: Clock, label: 'Pending' };
            case 'running':
                return { variant: 'default' as const, icon: Loader2, label: 'Running' };
            case 'completed':
                return { variant: 'default' as const, icon: CheckCircle, label: 'Completed' };
            case 'failed':
                return { variant: 'destructive' as const, icon: XCircle, label: 'Failed' };
            default:
                return { variant: 'secondary' as const, icon: Clock, label: status };
        }
    };

    const config = getStatusConfig(status);
    const Icon = config.icon;

    return (
        <Badge variant={config.variant} className="flex items-center gap-1">
            <Icon className={`h-3 w-3 ${status === 'running' ? 'animate-spin' : ''}`} />
            {config.label}
        </Badge>
    );
};

const FileViewer: React.FC<{
    files: Record<string, string>;
    title: string;
}> = ({ files, title }) => {
    const { toast } = useToast();

    const copyToClipboard = async (content: string) => {
        try {
            await navigator.clipboard.writeText(content);
            toast({
                title: "Copied to clipboard",
                description: "Code has been copied to your clipboard.",
            });
        } catch (error) {
            toast({
                title: "Failed to copy",
                description: "Could not copy to clipboard.",
                variant: "destructive",
            });
        }
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    {title}
                </CardTitle>
            </CardHeader>
            <CardContent>
                <Tabs defaultValue={Object.keys(files)[0]} className="w-full">
                    <TabsList className="grid w-full grid-cols-auto">
                        {Object.keys(files).map((filename) => (
                            <TabsTrigger key={filename} value={filename} className="text-xs">
                                {filename}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                    {Object.entries(files).map(([filename, content]) => (
                        <TabsContent key={filename} value={filename} className="mt-4">
                            <div className="relative">
                                <Button
                                    size="sm"
                                    variant="outline"
                                    className="absolute top-2 right-2 z-10"
                                    onClick={() => copyToClipboard(content)}
                                >
                                    <Copy className="h-3 w-3" />
                                </Button>
                                <pre className="bg-muted p-4 rounded-lg overflow-auto text-sm max-h-96">
                                    <code>{content}</code>
                                </pre>
                            </div>
                        </TabsContent>
                    ))}
                </Tabs>
            </CardContent>
        </Card>
    );
};

export const CodeGenerator: React.FC<CodeGeneratorProps> = ({
    projectId,
    className
}) => {
    const [activeTab, setActiveTab] = useState<'form' | 'result'>('form');

    const form = useForm<FormData>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            query: '',
            scenario: 'NEW_RESOURCE',
            project_id: projectId,
            save_to_project: true,
            provider_type: 'aws',
            temperature: 0.7,
            max_tokens: 2048,
        },
    });

    const {
        startGeneration,
        reset,
        jobId,
        jobStatus,
        result,
        isGenerating,
        isPolling,
        error,
    } = useCodeGenerationFlow();

    const onSubmit = async (data: FormData) => {
        try {
            const request: CodeGenerationRequest = {
                ...data,
                project_id: projectId || data.project_id,
            };

            await startGeneration(request);
            setActiveTab('result');
        } catch (error) {
            // Error is handled by the hook
        }
    };

    const handleReset = () => {
        reset();
        setActiveTab('form');
        form.reset();
    };

    const getProgress = () => {
        if (!jobStatus) return 0;
        if (jobStatus.progress) return jobStatus.progress;

        switch (jobStatus.status) {
            case 'pending': return 10;
            case 'running': return 50;
            case 'completed': return 100;
            case 'failed': return 100;
            default: return 0;
        }
    };

    return (
        <Card className={className}>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Code className="h-5 w-5" />
                    Code Generator
                </CardTitle>
                <CardDescription>
                    Generate Terraform infrastructure code using AI
                </CardDescription>
            </CardHeader>
            <CardContent>
                <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
                    <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="form">Configuration</TabsTrigger>
                        <TabsTrigger value="result" disabled={!jobId}>
                            Results {jobId && <Badge variant="secondary" className="ml-2">{jobStatus?.status}</Badge>}
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="form" className="space-y-4">
                        <Form {...form}>
                            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                                <FormField
                                    control={form.control}
                                    name="query"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Infrastructure Description</FormLabel>
                                            <FormControl>
                                                <Textarea
                                                    placeholder="Describe the infrastructure you want to create (e.g., 'Create an S3 bucket with versioning enabled and a CloudFront distribution')"
                                                    className="min-h-[100px]"
                                                    {...field}
                                                />
                                            </FormControl>
                                            <FormDescription>
                                                Be specific about the resources, configurations, and requirements
                                            </FormDescription>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <div className="grid grid-cols-2 gap-4">
                                    <FormField
                                        control={form.control}
                                        name="scenario"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel>Scenario</FormLabel>
                                                <Select onValueChange={field.onChange} defaultValue={field.value}>
                                                    <FormControl>
                                                        <SelectTrigger>
                                                            <SelectValue />
                                                        </SelectTrigger>
                                                    </FormControl>
                                                    <SelectContent>
                                                        <SelectItem value="NEW_RESOURCE">New Resource</SelectItem>
                                                        <SelectItem value="MODIFY_EXISTING">Modify Existing</SelectItem>
                                                        <SelectItem value="TROUBLESHOOT">Troubleshoot</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />

                                    <FormField
                                        control={form.control}
                                        name="provider_type"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel>Provider</FormLabel>
                                                <Select onValueChange={field.onChange} defaultValue={field.value}>
                                                    <FormControl>
                                                        <SelectTrigger>
                                                            <SelectValue />
                                                        </SelectTrigger>
                                                    </FormControl>
                                                    <SelectContent>
                                                        <SelectItem value="aws">AWS</SelectItem>
                                                        <SelectItem value="azure">Azure</SelectItem>
                                                        <SelectItem value="gcp">Google Cloud</SelectItem>
                                                        <SelectItem value="kubernetes">Kubernetes</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />
                                </div>

                                {form.watch('scenario') === 'MODIFY_EXISTING' && (
                                    <FormField
                                        control={form.control}
                                        name="existing_code"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel>Existing Code</FormLabel>
                                                <FormControl>
                                                    <Textarea
                                                        placeholder="Paste your existing Terraform code here..."
                                                        className="min-h-[150px] font-mono text-sm"
                                                        {...field}
                                                    />
                                                </FormControl>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />
                                )}

                                <FormField
                                    control={form.control}
                                    name="target_file_path"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Target File Path (Optional)</FormLabel>
                                            <FormControl>
                                                <Input placeholder="main.tf" {...field} />
                                            </FormControl>
                                            <FormDescription>
                                                Specify the file name for the generated code
                                            </FormDescription>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                {projectId && (
                                    <FormField
                                        control={form.control}
                                        name="save_to_project"
                                        render={({ field }) => (
                                            <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                                                <div className="space-y-0.5">
                                                    <FormLabel className="text-base">
                                                        Save to Project
                                                    </FormLabel>
                                                    <FormDescription>
                                                        Save generated files to the current project
                                                    </FormDescription>
                                                </div>
                                                <FormControl>
                                                    <Switch
                                                        checked={field.value}
                                                        onCheckedChange={field.onChange}
                                                    />
                                                </FormControl>
                                            </FormItem>
                                        )}
                                    />
                                )}

                                <div className="flex justify-end space-x-2">
                                    {jobId && (
                                        <Button type="button" variant="outline" onClick={handleReset}>
                                            Reset
                                        </Button>
                                    )}
                                    <Button
                                        type="submit"
                                        disabled={isGenerating}
                                        className="flex items-center gap-2"
                                    >
                                        {isGenerating ? (
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                        ) : (
                                            <Play className="h-4 w-4" />
                                        )}
                                        Generate Code
                                    </Button>
                                </div>
                            </form>
                        </Form>
                    </TabsContent>

                    <TabsContent value="result" className="space-y-4">
                        {jobId && (
                            <div className="space-y-4">
                                {/* Status Section */}
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="flex items-center justify-between">
                                            <span>Generation Status</span>
                                            <StatusBadge status={jobStatus?.status || 'pending'} />
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-2">
                                            <Progress value={getProgress()} className="w-full" />
                                            {jobStatus?.message && (
                                                <p className="text-sm text-muted-foreground">{jobStatus.message}</p>
                                            )}
                                            {isPolling && (
                                                <p className="text-sm text-muted-foreground flex items-center gap-2">
                                                    <Loader2 className="h-3 w-3 animate-spin" />
                                                    Checking status...
                                                </p>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>

                                {/* Results Section */}
                                {result && (
                                    <div className="space-y-4">
                                        {result.generated_files && (
                                            <FileViewer
                                                files={result.generated_files}
                                                title="Generated Files"
                                            />
                                        )}

                                        {result.github_status && (
                                            <Card>
                                                <CardHeader>
                                                    <CardTitle className="flex items-center gap-2">
                                                        <Github className="h-5 w-5" />
                                                        GitHub Status
                                                    </CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                    <div className="space-y-2">
                                                        <div className="flex items-center justify-between">
                                                            <span>Repository Push:</span>
                                                            <Badge variant={result.github_status.pushed ? 'default' : 'destructive'}>
                                                                {result.github_status.pushed ? 'Success' : 'Failed'}
                                                            </Badge>
                                                        </div>
                                                        {result.github_status.repo_url && (
                                                            <div className="flex items-center justify-between">
                                                                <span>Repository:</span>
                                                                <a
                                                                    href={result.github_status.repo_url}
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className="text-blue-600 hover:underline"
                                                                >
                                                                    View on GitHub
                                                                </a>
                                                            </div>
                                                        )}
                                                        {result.github_status.commit_sha && (
                                                            <div className="flex items-center justify-between">
                                                                <span>Commit:</span>
                                                                <code className="text-sm bg-muted px-2 py-1 rounded">
                                                                    {result.github_status.commit_sha.substring(0, 8)}
                                                                </code>
                                                            </div>
                                                        )}
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        )}

                                        {result.processing_time_ms && (
                                            <div className="text-sm text-muted-foreground text-center">
                                                Generated in {result.processing_time_ms}ms
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Error Section */}
                                {(error || result?.error_message) && (
                                    <Card className="border-red-200">
                                        <CardHeader>
                                            <CardTitle className="text-red-600 flex items-center gap-2">
                                                <XCircle className="h-5 w-5" />
                                                Generation Failed
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <p className="text-red-600">
                                                {error?.message || result?.error_message}
                                            </p>
                                        </CardContent>
                                    </Card>
                                )}
                            </div>
                        )}
                    </TabsContent>
                </Tabs>
            </CardContent>
        </Card>
    );
};