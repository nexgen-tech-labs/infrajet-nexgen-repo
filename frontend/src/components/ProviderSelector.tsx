import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Cloud, Server, Database, Settings, CheckCircle, Clock, Zap, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { useChat } from "@/contexts/ChatContext";

interface ProviderSelectorProps {
  selectedProvider: string;
  onProviderChange: (provider: string) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

const providers = [
  {
    id: "aws",
    name: "AWS",
    fullName: "Amazon Web Services",
    icon: Cloud,
    color: "bg-gradient-to-r from-orange-500 to-orange-600",
    bgColor: "bg-orange-50 dark:bg-orange-950/20",
    textColor: "text-orange-700 dark:text-orange-300",
    borderColor: "border-orange-200 dark:border-orange-800",
    description: "Comprehensive cloud platform"
  },
  {
    id: "azure",
    name: "Azure",
    fullName: "Microsoft Azure",
    icon: Server,
    color: "bg-gradient-to-r from-blue-500 to-blue-600",
    bgColor: "bg-blue-50 dark:bg-blue-950/20",
    textColor: "text-blue-700 dark:text-blue-300",
    borderColor: "border-blue-200 dark:border-blue-800",
    description: "Enterprise cloud solutions"
  },
  {
    id: "gcp",
    name: "GCP",
    fullName: "Google Cloud Platform",
    icon: Database,
    color: "bg-gradient-to-r from-green-500 to-green-600",
    bgColor: "bg-green-50 dark:bg-green-950/20",
    textColor: "text-green-700 dark:text-green-300",
    borderColor: "border-green-200 dark:border-green-800",
    description: "AI-first cloud platform"
  },
  {
    id: "terraform",
    name: "Terraform",
    fullName: "HashiCorp Terraform",
    icon: Settings,
    color: "bg-gradient-to-r from-purple-500 to-purple-600",
    bgColor: "bg-purple-50 dark:bg-purple-950/20",
    textColor: "text-purple-700 dark:text-purple-300",
    borderColor: "border-purple-200 dark:border-purple-800",
    description: "Infrastructure as Code"
  }
];

const ProviderSelector = ({
  selectedProvider,
  onProviderChange,
  isCollapsed = false,
  onToggleCollapse
}: ProviderSelectorProps) => {
  const { messages, isLoading } = useChat();
  const selectedProviderInfo = providers.find(p => p.id === selectedProvider);
  const SelectedIcon = selectedProviderInfo?.icon || Cloud;

  // Get the latest generation status
  const codeMessages = messages.filter(msg => msg.isCode);
  const hasGenerated = codeMessages.length > 0;

  return (
    <Collapsible open={!isCollapsed} onOpenChange={onToggleCollapse}>
      {isCollapsed && (
        <CollapsibleTrigger asChild>
          <Button
            variant="outline"
            className="w-full justify-between h-auto p-3 hover:bg-muted/50 transition-all duration-200"
          >
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${selectedProviderInfo?.color || 'bg-muted'}`}>
                <SelectedIcon className="w-4 h-4 text-white" />
              </div>
              <div className="text-left">
                <div className="font-medium text-sm">{selectedProviderInfo?.name || "Select"}</div>
                <div className="text-xs text-muted-foreground">{selectedProviderInfo?.fullName || "Provider"}</div>
              </div>
            </div>
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          </Button>
        </CollapsibleTrigger>
      )}
      <CollapsibleContent className="space-y-4 p-6 transition-all duration-300 ease-in-out">
        {/* Current Selection Display */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${selectedProviderInfo?.color || 'bg-muted'}`}>
              <SelectedIcon className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">
                {selectedProviderInfo?.fullName || "Select Provider"}
              </h3>
              <p className="text-sm text-muted-foreground">
                {selectedProviderInfo?.description || "Choose your cloud platform"}
              </p>
            </div>
          </div>

          {/* Status Badge */}
          <div className="flex items-center gap-2">
            {isLoading ? (
              <Badge variant="secondary" className="gap-1">
                <Clock className="w-3 h-3 animate-spin" />
                Generating
              </Badge>
            ) : hasGenerated ? (
              <Badge variant="default" className="gap-1 bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400">
                <CheckCircle className="w-3 h-3" />
                Ready
              </Badge>
            ) : (
              <Badge variant="outline" className="gap-1">
                <Zap className="w-3 h-3" />
                Ready
              </Badge>
            )}
          </div>
        </div>

        {/* Provider Selection Grid */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">Cloud Provider</label>
          <div className="grid grid-cols-2 gap-2">
            {providers.map(provider => {
              const Icon = provider.icon;
              const isSelected = selectedProvider === provider.id;

              return (
                <Button
                  key={provider.id}
                  variant="outline"
                  onClick={() => onProviderChange(provider.id)}
                  className={`h-auto p-3 justify-start transition-all duration-200 ${isSelected
                    ? `${provider.bgColor} ${provider.borderColor} ${provider.textColor} border-2 shadow-sm`
                    : 'hover:bg-muted/50 border-border'
                    }`}
                >
                  <div className="flex items-center gap-2 w-full">
                    <div className={`p-1.5 rounded-md ${isSelected ? provider.color : 'bg-muted'}`}>
                      <Icon className={`w-4 h-4 ${isSelected ? 'text-white' : 'text-muted-foreground'}`} />
                    </div>
                    <div className="text-left">
                      <div className="font-medium text-sm">{provider.name}</div>
                      <div className="text-xs opacity-70">{provider.description}</div>
                    </div>
                  </div>
                </Button>
              );
            })}
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};

export default ProviderSelector;