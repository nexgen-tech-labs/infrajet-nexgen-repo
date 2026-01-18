import React from 'react';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Loader2 } from 'lucide-react';

interface GenerationProgressProps {
  status: string;
  progressPercentage: number;
  currentStep: string;
}

export const GenerationProgress: React.FC<GenerationProgressProps> = ({
  status,
  progressPercentage,
  currentStep,
}) => {
  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
        return 'bg-green-500';
      case 'error':
        return 'bg-red-500';
      case 'in_progress':
      case 'generating':
        return 'bg-blue-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
    switch (status.toLowerCase()) {
      case 'completed':
        return 'default';
      case 'error':
        return 'destructive';
      case 'in_progress':
      case 'generating':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  return (
    <div className="space-y-3 p-4 border rounded-lg bg-muted/50">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {status === 'in_progress' || status === 'generating' ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : null}
          <span className="font-medium">Generation Progress</span>
        </div>
        <Badge variant={getStatusVariant(status)}>
          {status.replace('_', ' ').toUpperCase()}
        </Badge>
      </div>

      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span>Progress</span>
          <span>{Math.round(progressPercentage)}%</span>
        </div>
        <Progress value={progressPercentage} className="h-2" />
      </div>

      {currentStep && (
        <div className="text-sm text-muted-foreground">
          <span className="font-medium">Current Step:</span> {currentStep}
        </div>
      )}
    </div>
  );
};