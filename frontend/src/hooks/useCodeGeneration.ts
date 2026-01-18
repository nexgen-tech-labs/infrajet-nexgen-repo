import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { codeGenerationApi, CodeGenerationRequest, JobResult } from '@/services/infrajetApi';
import { useToast } from '@/hooks/use-toast';
import { useCallback, useEffect, useState } from 'react';

// Query Keys
export const codeGenerationKeys = {
    all: ['codeGeneration'] as const,
    jobs: () => [...codeGenerationKeys.all, 'jobs'] as const,
    job: (jobId: string) => [...codeGenerationKeys.jobs(), jobId] as const,
    jobStatus: (jobId: string) => [...codeGenerationKeys.job(jobId), 'status'] as const,
    jobResult: (jobId: string) => [...codeGenerationKeys.job(jobId), 'result'] as const,
};

// Hooks
export const useGenerateCode = () => {
    const { toast } = useToast();

    return useMutation({
        mutationFn: (data: CodeGenerationRequest) => codeGenerationApi.generate(data),
        onSuccess: (data) => {
            toast({
                title: "Code generation started",
                description: data.message,
            });
        },
        onError: (error: Error) => {
            toast({
                title: "Failed to start code generation",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};

export const useJobStatus = (jobId: string, enabled: boolean = true) => {
    return useQuery({
        queryKey: codeGenerationKeys.jobStatus(jobId),
        queryFn: () => codeGenerationApi.getJobStatus(jobId),
        enabled: enabled && !!jobId,
        refetchInterval: (data) => {
            // Stop polling if job is completed or failed
            if (data?.status === 'completed' || data?.status === 'failed') {
                return false;
            }
            return 2000; // Poll every 2 seconds
        },
        staleTime: 0, // Always fetch fresh data
    });
};

export const useJobResult = (jobId: string, enabled: boolean = false) => {
    return useQuery({
        queryKey: codeGenerationKeys.jobResult(jobId),
        queryFn: () => codeGenerationApi.getJobResult(jobId),
        enabled: enabled && !!jobId,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
};

export const useValidateCode = () => {
    const { toast } = useToast();

    return useMutation({
        mutationFn: (code: string) => codeGenerationApi.validateCode(code),
        onError: (error: Error) => {
            toast({
                title: "Code validation failed",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};

export const useGenerateDiff = () => {
    const { toast } = useToast();

    return useMutation({
        mutationFn: ({ oldCode, newCode }: { oldCode: string; newCode: string }) =>
            codeGenerationApi.generateDiff(oldCode, newCode),
        onError: (error: Error) => {
            toast({
                title: "Failed to generate diff",
                description: error.message,
                variant: "destructive",
            });
        },
    });
};

// Custom hook for managing the complete code generation flow
export const useCodeGenerationFlow = () => {
    const [currentJobId, setCurrentJobId] = useState<string | null>(null);
    const [result, setResult] = useState<JobResult | null>(null);

    const generateMutation = useGenerateCode();
    const { data: jobStatus, isLoading: isPolling } = useJobStatus(
        currentJobId || '',
        !!currentJobId
    );
    const { data: jobResult, refetch: refetchResult } = useJobResult(
        currentJobId || '',
        jobStatus?.status === 'completed'
    );

    // Start code generation
    const startGeneration = useCallback(async (request: CodeGenerationRequest) => {
        try {
            const response = await generateMutation.mutateAsync(request);
            setCurrentJobId(response.job_id);
            setResult(null);
            return response;
        } catch (error) {
            throw error;
        }
    }, [generateMutation]);

    // Fetch result when job completes
    useEffect(() => {
        if (jobStatus?.status === 'completed' && currentJobId) {
            refetchResult().then(({ data }) => {
                if (data) {
                    setResult(data);
                }
            });
        }
    }, [jobStatus?.status, currentJobId, refetchResult]);

    // Reset state
    const reset = useCallback(() => {
        setCurrentJobId(null);
        setResult(null);
    }, []);

    return {
        startGeneration,
        reset,
        jobId: currentJobId,
        jobStatus,
        result: result || jobResult,
        isGenerating: generateMutation.isPending,
        isPolling,
        error: generateMutation.error,
    };
};