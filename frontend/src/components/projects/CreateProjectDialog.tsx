import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import {
    Form,
    FormControl,
    FormDescription,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { useCreateProject } from '@/hooks/useProjects';
import { useGitHubIntegrationFlow } from '@/hooks/useGitHubIntegration';
import { CreateProjectRequest } from '@/services/infrajetApi';

const formSchema = z.object({
    name: z.string().min(1, 'Project name is required').max(100, 'Name too long'),
    description: z.string().min(1, 'Description is required').max(500, 'Description too long'),
    link_to_github: z.boolean().default(false),
    github_installation_id: z.number().optional(),
});

type FormData = z.infer<typeof formSchema>;

interface CreateProjectDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    githubToken?: string;
}

export const CreateProjectDialog: React.FC<CreateProjectDialogProps> = ({
    open,
    onOpenChange,
    githubToken,
}) => {
    const [step, setStep] = useState<'project' | 'github'>('project');

    const form = useForm<FormData>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            name: '',
            description: '',
            link_to_github: false,
        },
    });

    const createMutation = useCreateProject();
    const { installations, loadingInstallations } = useGitHubIntegrationFlow('', githubToken);

    const watchLinkToGitHub = form.watch('link_to_github');

    const onSubmit = async (data: FormData) => {
        if (data.link_to_github && !data.github_installation_id) {
            setStep('github');
            return;
        }

        const request: CreateProjectRequest = {
            name: data.name,
            description: data.description,
            link_to_github: data.link_to_github,
            github_installation_id: data.github_installation_id,
        };

        try {
            await createMutation.mutateAsync(request);
            onOpenChange(false);
            form.reset();
            setStep('project');
        } catch (error) {
            // Error is handled by the mutation
        }
    };

    const handleBack = () => {
        setStep('project');
    };

    const handleClose = () => {
        onOpenChange(false);
        form.reset();
        setStep('project');
    };

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>
                        {step === 'project' ? 'Create New Project' : 'GitHub Integration'}
                    </DialogTitle>
                    <DialogDescription>
                        {step === 'project'
                            ? 'Create a new infrastructure project to organize your Terraform code.'
                            : 'Select a GitHub installation to link your project.'
                        }
                    </DialogDescription>
                </DialogHeader>

                <Form {...form}>
                    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                        {step === 'project' && (
                            <>
                                <FormField
                                    control={form.control}
                                    name="name"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Project Name</FormLabel>
                                            <FormControl>
                                                <Input placeholder="My Terraform Project" {...field} />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="description"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Description</FormLabel>
                                            <FormControl>
                                                <Textarea
                                                    placeholder="Describe your infrastructure project..."
                                                    className="resize-none"
                                                    {...field}
                                                />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="link_to_github"
                                    render={({ field }) => (
                                        <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                                            <div className="space-y-0.5">
                                                <FormLabel className="text-base">
                                                    Link to GitHub
                                                </FormLabel>
                                                <FormDescription>
                                                    Create a GitHub repository for this project
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

                                <div className="flex justify-end space-x-2">
                                    <Button type="button" variant="outline" onClick={handleClose}>
                                        Cancel
                                    </Button>
                                    <Button
                                        type="submit"
                                        disabled={createMutation.isPending}
                                    >
                                        {watchLinkToGitHub ? 'Next' : 'Create Project'}
                                    </Button>
                                </div>
                            </>
                        )}

                        {step === 'github' && (
                            <>
                                <FormField
                                    control={form.control}
                                    name="github_installation_id"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>GitHub Installation</FormLabel>
                                            <Select
                                                onValueChange={(value) => field.onChange(parseInt(value))}
                                                disabled={loadingInstallations}
                                            >
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select GitHub installation..." />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent>
                                                    {installations.map((installation) => (
                                                        <SelectItem
                                                            key={installation.id}
                                                            value={installation.id.toString()}
                                                        >
                                                            {installation.account_login} ({installation.account_type})
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                            <FormDescription>
                                                Choose the GitHub account or organization where the repository will be created.
                                            </FormDescription>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <div className="flex justify-between">
                                    <Button type="button" variant="outline" onClick={handleBack}>
                                        Back
                                    </Button>
                                    <div className="space-x-2">
                                        <Button type="button" variant="outline" onClick={handleClose}>
                                            Cancel
                                        </Button>
                                        <Button
                                            type="submit"
                                            disabled={createMutation.isPending || !form.watch('github_installation_id')}
                                        >
                                            {createMutation.isPending ? 'Creating...' : 'Create Project'}
                                        </Button>
                                    </div>
                                </div>
                            </>
                        )}
                    </form>
                </Form>
            </DialogContent>
        </Dialog>
    );
};