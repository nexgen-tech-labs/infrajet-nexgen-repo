import { useEffect, useState } from 'react';
import { AdminLayout } from '@/components/admin/AdminLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { supabase } from '@/integrations/supabase/client';
import { AlertTriangle, CheckCircle, Plus, X } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { useAdminAuth } from '@/contexts/AdminAuthContext';

interface SystemAlert {
  id: string;
  title: string;
  message: string;
  alert_type: 'info' | 'warning' | 'error' | 'success';
  severity: 'low' | 'medium' | 'high' | 'critical';
  is_resolved: boolean;
  created_at: string;
  resolved_at: string | null;
}

const SystemAlerts = () => {
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const { adminUser } = useAdminAuth();

  useEffect(() => {
    fetchAlerts();
  }, []);

  const fetchAlerts = async () => {
    try {
      const { data, error } = await supabase
        .from('system_alerts')
        .select('*')
        .order('created_at', { ascending: false });

      if (error) throw error;
      setAlerts((data || []) as SystemAlert[]);
    } catch (error) {
      console.error('Error fetching alerts:', error);
      toast({
        title: "Error",
        description: "Failed to fetch system alerts",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const resolveAlert = async (alertId: string) => {
    try {
      const { error } = await supabase
        .from('system_alerts')
        .update({ 
          is_resolved: true, 
          resolved_at: new Date().toISOString(),
          resolved_by: adminUser?.id 
        })
        .eq('id', alertId);

      if (error) throw error;
      
      await fetchAlerts();
      toast({
        title: "Success",
        description: "Alert resolved successfully",
      });
    } catch (error) {
      console.error('Error resolving alert:', error);
      toast({
        title: "Error",
        description: "Failed to resolve alert",
        variant: "destructive",
      });
    }
  };

  const createTestAlert = async () => {
    try {
      const { error } = await supabase
        .from('system_alerts')
        .insert({
          title: 'Test Alert',
          message: 'This is a test system alert created for demonstration purposes.',
          alert_type: 'warning',
          severity: 'medium'
        });

      if (error) throw error;
      
      await fetchAlerts();
      toast({
        title: "Success",
        description: "Test alert created successfully",
      });
    } catch (error) {
      console.error('Error creating test alert:', error);
      toast({
        title: "Error",
        description: "Failed to create test alert",
        variant: "destructive",
      });
    }
  };

  const getAlertVariant = (type: string, severity: string): 'default' | 'destructive' => {
    if (type === 'error' || severity === 'critical') return 'destructive';
    return 'default';
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-500';
      case 'high': return 'bg-orange-500';
      case 'medium': return 'bg-yellow-500';
      case 'low': return 'bg-blue-500';
      default: return 'bg-gray-500';
    }
  };

  const unresolvedAlerts = alerts.filter(alert => !alert.is_resolved);
  const resolvedAlerts = alerts.filter(alert => alert.is_resolved);

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-foreground">System Alerts</h1>
            <p className="text-muted-foreground">
              Monitor and manage system alerts and warnings
            </p>
          </div>
          <Button onClick={createTestAlert}>
            <Plus className="mr-2 h-4 w-4" />
            Create Test Alert
          </Button>
        </div>

        {/* Summary Cards */}
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Total Alerts</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{alerts.length}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Unresolved</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{unresolvedAlerts.length}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Critical</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-700">
                {alerts.filter(a => a.severity === 'critical' && !a.is_resolved).length}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Resolved Today</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {alerts.filter(a => a.is_resolved && a.resolved_at && 
                  new Date(a.resolved_at).toDateString() === new Date().toDateString()).length}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Unresolved Alerts */}
        {unresolvedAlerts.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-red-500" />
                Unresolved Alerts ({unresolvedAlerts.length})
              </CardTitle>
              <CardDescription>
                Active system alerts that require attention
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {unresolvedAlerts.map((alert) => (
                <Alert key={alert.id} variant={getAlertVariant(alert.alert_type, alert.severity)}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-semibold">{alert.title}</h4>
                        <Badge 
                          variant="outline" 
                          className={`${getSeverityColor(alert.severity)} text-white border-0`}
                        >
                          {alert.severity}
                        </Badge>
                        <Badge variant="outline">{alert.alert_type}</Badge>
                      </div>
                      <AlertDescription>{alert.message}</AlertDescription>
                      <div className="text-xs text-muted-foreground mt-2">
                        Created: {new Date(alert.created_at).toLocaleString()}
                      </div>
                    </div>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={() => resolveAlert(alert.id)}
                      className="ml-4"
                    >
                      <CheckCircle className="h-3 w-3 mr-1" />
                      Resolve
                    </Button>
                  </div>
                </Alert>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Resolved Alerts */}
        {resolvedAlerts.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-green-500" />
                Resolved Alerts ({resolvedAlerts.length})
              </CardTitle>
              <CardDescription>
                Previously resolved system alerts
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {resolvedAlerts.slice(0, 5).map((alert) => (
                <div key={alert.id} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                  <div>
                    <div className="font-medium">{alert.title}</div>
                    <div className="text-sm text-muted-foreground">{alert.message}</div>
                    <div className="text-xs text-muted-foreground">
                      Resolved: {alert.resolved_at ? new Date(alert.resolved_at).toLocaleString() : 'Unknown'}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Badge variant="outline">{alert.severity}</Badge>
                    <Badge variant="outline">{alert.alert_type}</Badge>
                  </div>
                </div>
              ))}
              {resolvedAlerts.length > 5 && (
                <div className="text-center text-sm text-muted-foreground">
                  And {resolvedAlerts.length - 5} more resolved alerts...
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {loading && (
          <div className="text-center py-8">Loading system alerts...</div>
        )}
      </div>
    </AdminLayout>
  );
};

export default SystemAlerts;