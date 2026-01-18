import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  Settings, 
  Globe, 
  BarChart3, 
  Zap, 
  BookOpen, 
  Shield, 
  Users, 
  CreditCard, 
  User, 
  FlaskConical,
  Database,
  Github,
  ExternalLink,
  ChevronRight
} from 'lucide-react';

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SettingsDialog = ({ open, onOpenChange }: SettingsDialogProps) => {
  const projectSettings = [
    { icon: Settings, label: 'Project Settings', description: 'General project configuration' },
    { icon: Globe, label: 'Cloud Settings', description: 'Manage Cloud Integration' },
    { icon: BarChart3, label: 'Analytics', description: 'View project analytics' },
    { icon: Zap, label: 'Page Speed', description: 'Performance optimization' },
    { icon: BookOpen, label: 'Knowledge', description: 'Documentation and guides' },
    { icon: Shield, label: 'Security', description: 'Security settings and policies' },
  ];

  const workspaceSettings = [
    { icon: Users, label: 'People', description: 'Manage team members', badge: '2 people' },
    { icon: CreditCard, label: 'Plans & Billing', description: 'Subscription and billing' },
  ];

  const accountSettings = [
    { icon: User, label: 'Profile', description: 'Personal account settings' },
    { icon: FlaskConical, label: 'Labs', description: 'Experimental features' },
  ];

  const integrations = [
    { icon: Database, label: 'Supabase', description: 'Database integration', status: 'Connected' },
    { icon: Github, label: 'GitHub', description: 'Version control integration', status: 'Connected' },
  ];

  const SettingSection = ({ title, items }: { title: string; items: any[] }) => (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
        {title}
      </h3>
      <div className="space-y-1">
        {items.map((item, index) => (
          <Button
            key={index}
            variant="ghost"
            className="w-full justify-start h-auto p-3 text-left hover:bg-accent/50"
          >
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center">
                <item.icon className="w-4 h-4 mr-3 text-muted-foreground" />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground">{item.label}</span>
                    {item.badge && (
                      <Badge variant="secondary" className="text-xs">
                        {item.badge}
                      </Badge>
                    )}
                    {item.status && (
                      <Badge 
                        variant={item.status === 'Connected' ? 'default' : 'secondary'} 
                        className="text-xs"
                      >
                        {item.status}
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{item.description}</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            </div>
          </Button>
        ))}
      </div>
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-background border-border max-w-md max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-foreground">
            <Settings className="w-5 h-5" />
            Settings
          </DialogTitle>
        </DialogHeader>
        <ScrollArea className="max-h-[60vh] pr-4">
          <div className="space-y-6">
            <SettingSection title="Project" items={projectSettings} />
            <Separator />
            <SettingSection title="Workspace" items={workspaceSettings} />
            <Separator />
            <SettingSection title="Account" items={accountSettings} />
            <Separator />
            <SettingSection title="Integrations" items={integrations} />
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
};

export default SettingsDialog;