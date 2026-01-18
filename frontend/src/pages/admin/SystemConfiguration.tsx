import { useEffect, useState } from 'react';
import { AdminLayout } from '@/components/admin/AdminLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { supabase } from '@/integrations/supabase/client';
import { Settings, Save, RotateCcw } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { useAdminAuth } from '@/contexts/AdminAuthContext';

interface SystemConfig {
  id: string;
  config_key: string;
  config_value: any;
  description: string;
}

const SystemConfiguration = () => {
  const [configs, setConfigs] = useState<SystemConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();
  const { adminUser } = useAdminAuth();

  // Default configuration values
  const defaultConfigs = [
    {
      key: 'max_projects_per_user',
      value: 5,
      description: 'Maximum number of projects each user can create',
      type: 'number'
    },
    {
      key: 'default_credits_new_user',
      value: 10,
      description: 'Default credits assigned to new users',
      type: 'number'
    },
    {
      key: 'maintenance_mode',
      value: false,
      description: 'Enable maintenance mode to restrict access',
      type: 'boolean'
    },
    {
      key: 'maintenance_message',
      value: 'System is under maintenance. Please check back later.',
      description: 'Message displayed during maintenance mode',
      type: 'text'
    },
    {
      key: 'registration_enabled',
      value: true,
      description: 'Allow new user registrations',
      type: 'boolean'
    },
    {
      key: 'github_integration_enabled',
      value: true,
      description: 'Enable GitHub integration features',
      type: 'boolean'
    },
    {
      key: 'support_email',
      value: 'support@yourapp.com',
      description: 'Support contact email address',
      type: 'text'
    },
    {
      key: 'max_file_upload_size',
      value: 10,
      description: 'Maximum file upload size in MB',
      type: 'number'
    }
  ];

  useEffect(() => {
    fetchConfigs();
  }, []);

  const fetchConfigs = async () => {
    try {
      const { data, error } = await supabase
        .from('system_configurations')
        .select('*')
        .order('config_key');

      if (error) throw error;
      setConfigs(data || []);
    } catch (error) {
      console.error('Error fetching configurations:', error);
      toast({
        title: "Error",
        description: "Failed to fetch system configurations",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const updateConfig = async (key: string, value: any) => {
    setSaving(true);
    try {
      const { error } = await supabase
        .from('system_configurations')
        .upsert({
          config_key: key,
          config_value: value,
          description: defaultConfigs.find(c => c.key === key)?.description || '',
          updated_by: adminUser?.id
        }, {
          onConflict: 'config_key'
        });

      if (error) throw error;

      await fetchConfigs();
      toast({
        title: "Success",
        description: "Configuration updated successfully",
      });
    } catch (error) {
      console.error('Error updating configuration:', error);
      toast({
        title: "Error",
        description: "Failed to update configuration",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const getConfigValue = (key: string) => {
    const config = configs.find(c => c.config_key === key);
    const defaultConfig = defaultConfigs.find(c => c.key === key);
    return config?.config_value ?? defaultConfig?.value ?? '';
  };

  const handleConfigChange = (key: string, value: any, type: string) => {
    let processedValue = value;
    if (type === 'number') {
      processedValue = parseFloat(value) || 0;
    } else if (type === 'boolean') {
      processedValue = Boolean(value);
    }
    updateConfig(key, processedValue);
  };

  const resetToDefaults = async () => {
    setSaving(true);
    try {
      for (const config of defaultConfigs) {
        await supabase
          .from('system_configurations')
          .upsert({
            config_key: config.key,
            config_value: config.value,
            description: config.description,
            updated_by: adminUser?.id
          }, {
            onConflict: 'config_key'
          });
      }

      await fetchConfigs();
      toast({
        title: "Success",
        description: "All configurations reset to defaults",
      });
    } catch (error) {
      console.error('Error resetting configurations:', error);
      toast({
        title: "Error",
        description: "Failed to reset configurations",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-foreground">System Configuration</h1>
            <p className="text-muted-foreground">
              Manage global system settings and parameters
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={resetToDefaults} disabled={saving}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Reset to Defaults
            </Button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-8">Loading configurations...</div>
        ) : (
          <div className="grid gap-6">
            {/* User & Account Settings */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="h-5 w-5" />
                  User & Account Settings
                </CardTitle>
                <CardDescription>
                  Configure user registration and account limits
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="max_projects">Max Projects per User</Label>
                    <Input
                      id="max_projects"
                      type="number"
                      value={getConfigValue('max_projects_per_user')}
                      onChange={(e) => handleConfigChange('max_projects_per_user', e.target.value, 'number')}
                      disabled={saving}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="default_credits">Default Credits for New Users</Label>
                    <Input
                      id="default_credits"
                      type="number"
                      value={getConfigValue('default_credits_new_user')}
                      onChange={(e) => handleConfigChange('default_credits_new_user', e.target.value, 'number')}
                      disabled={saving}
                    />
                  </div>
                </div>

                <Separator />

                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>User Registration</Label>
                      <div className="text-sm text-muted-foreground">
                        Allow new users to register accounts
                      </div>
                    </div>
                    <Switch
                      checked={getConfigValue('registration_enabled')}
                      onCheckedChange={(checked) => handleConfigChange('registration_enabled', checked, 'boolean')}
                      disabled={saving}
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>GitHub Integration</Label>
                      <div className="text-sm text-muted-foreground">
                        Enable GitHub integration features
                      </div>
                    </div>
                    <Switch
                      checked={getConfigValue('github_integration_enabled')}
                      onCheckedChange={(checked) => handleConfigChange('github_integration_enabled', checked, 'boolean')}
                      disabled={saving}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* System Maintenance */}
            <Card>
              <CardHeader>
                <CardTitle>System Maintenance</CardTitle>
                <CardDescription>
                  Configure maintenance mode and system messages
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Maintenance Mode</Label>
                    <div className="text-sm text-muted-foreground">
                      Temporarily restrict access to the system
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={getConfigValue('maintenance_mode')}
                      onCheckedChange={(checked) => handleConfigChange('maintenance_mode', checked, 'boolean')}
                      disabled={saving}
                    />
                    <Badge variant={getConfigValue('maintenance_mode') ? 'destructive' : 'secondary'}>
                      {getConfigValue('maintenance_mode') ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="maintenance_message">Maintenance Message</Label>
                  <Textarea
                    id="maintenance_message"
                    value={getConfigValue('maintenance_message')}
                    onChange={(e) => handleConfigChange('maintenance_message', e.target.value, 'text')}
                    disabled={saving}
                    placeholder="Message shown to users during maintenance"
                  />
                </div>
              </CardContent>
            </Card>

            {/* General Settings */}
            <Card>
              <CardHeader>
                <CardTitle>General Settings</CardTitle>
                <CardDescription>
                  Configure general system parameters
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="support_email">Support Email</Label>
                    <Input
                      id="support_email"
                      type="email"
                      value={getConfigValue('support_email')}
                      onChange={(e) => handleConfigChange('support_email', e.target.value, 'text')}
                      disabled={saving}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="max_file_size">Max File Upload Size (MB)</Label>
                    <Input
                      id="max_file_size"
                      type="number"
                      value={getConfigValue('max_file_upload_size')}
                      onChange={(e) => handleConfigChange('max_file_upload_size', e.target.value, 'number')}
                      disabled={saving}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </AdminLayout>
  );
};

export default SystemConfiguration;