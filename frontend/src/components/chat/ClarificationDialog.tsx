import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';

interface ClarificationQuestion {
  id: string;
  question: string;
  type: 'text' | 'select' | 'boolean';
  options?: string[];
}

interface ClarificationDialogProps {
  isOpen: boolean;
  questions: ClarificationQuestion[];
  contextSummary: string;
  onRespond: (responses: { [key: string]: string }) => void;
  onCancel: () => void;
}

export const ClarificationDialog: React.FC<ClarificationDialogProps> = ({
  isOpen,
  questions,
  contextSummary,
  onRespond,
  onCancel,
}) => {
  const [responses, setResponses] = useState<{ [key: string]: string }>({});

  const handleResponseChange = (questionId: string, value: string) => {
    setResponses(prev => ({ ...prev, [questionId]: value }));
  };

  const handleSubmit = () => {
    onRespond(responses);
    setResponses({});
  };

  const handleCancel = () => {
    onCancel();
    setResponses({});
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleCancel}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto z-50">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold">Clarification Needed</DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {contextSummary && (
            <div className="p-4 bg-muted rounded-lg">
              <h4 className="font-medium mb-2">Context Summary</h4>
              <p className="text-sm text-muted-foreground">{contextSummary}</p>
            </div>
          )}

          <div className="space-y-4">
            {questions.map((question) => (
              <div key={question.id} className="space-y-2">
                <Label htmlFor={question.id}>{question.question}</Label>

                {question.type === 'text' && (
                  <Textarea
                    id={question.id}
                    value={responses[question.id] || ''}
                    onChange={(e) => handleResponseChange(question.id, e.target.value)}
                    placeholder="Enter your response..."
                    className="min-h-[80px] resize-none"
                  />
                )}

                {question.type === 'select' && question.options && (
                  <Select
                    value={responses[question.id] || ''}
                    onValueChange={(value) => handleResponseChange(question.id, value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select an option..." />
                    </SelectTrigger>
                    <SelectContent>
                      {question.options.map((option) => (
                        <SelectItem key={option} value={option}>
                          {option}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}

                {question.type === 'boolean' && (
                  <div className="flex items-center space-x-2">
                    <Switch
                      id={question.id}
                      checked={responses[question.id] === 'true'}
                      onCheckedChange={(checked) =>
                        handleResponseChange(question.id, checked.toString())
                      }
                    />
                    <Label htmlFor={question.id}>Yes</Label>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={handleCancel}>
              Cancel
            </Button>
            <Button onClick={handleSubmit}>
              Submit Responses
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};