import { useState } from 'react';
import { AdminLayout } from '@/components/admin/AdminLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { supabase } from '@/integrations/supabase/client';
import { Bot, TestTube, CheckCircle, XCircle, Activity } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

const OpenAIIntegration = () => {
  const [testPrompt, setTestPrompt] = useState('Hello, can you help me test the OpenAI integration?');
  const [testResponse, setTestResponse] = useState('');
  const [testing, setTesting] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'unknown' | 'connected' | 'error'>('unknown');
  const { toast } = useToast();

  const testOpenAIConnection = async () => {
    setTesting(true);
    setTestResponse('');
    
    try {
      const { data, error } = await supabase.functions.invoke('generate-iac-code', {
        body: { 
          requirements: testPrompt,
          // This will trigger the OpenAI call
          test: true 
        }
      });

      if (error) throw error;

      setTestResponse(JSON.stringify(data, null, 2));
      setConnectionStatus('connected');
      toast({
        title: "Success",
        description: "OpenAI integration is working correctly",
      });
    } catch (error) {
      console.error('OpenAI test error:', error);
      setConnectionStatus('error');
      setTestResponse(`Error: ${error.message || 'Failed to connect to OpenAI'}`);
      toast({
        title: "Error",
        description: "OpenAI integration test failed",
        variant: "destructive",
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-foreground">OpenAI Integration</h1>
          <p className="text-muted-foreground">
            Test and monitor OpenAI API connectivity and usage
          </p>
        </div>

        {/* Status Overview */}
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Connection Status</CardTitle>
              <Bot className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                {connectionStatus === 'connected' && (
                  <>
                    <CheckCircle className="h-5 w-5 text-green-500" />
                    <Badge variant="default" className="bg-green-500">Connected</Badge>
                  </>
                )}
                {connectionStatus === 'error' && (
                  <>
                    <XCircle className="h-5 w-5 text-red-500" />
                    <Badge variant="destructive">Error</Badge>
                  </>
                )}
                {connectionStatus === 'unknown' && (
                  <>
                    <Activity className="h-5 w-5 text-yellow-500" />
                    <Badge variant="secondary">Unknown</Badge>
                  </>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">API Usage Today</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">-</div>
              <p className="text-xs text-muted-foreground">Tokens consumed</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Last Test</CardTitle>
              <TestTube className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">-</div>
              <p className="text-xs text-muted-foreground">Never tested</p>
            </CardContent>
          </Card>
        </div>

        {/* Configuration Check */}
        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
            <CardDescription>
              Verify OpenAI API key configuration
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Alert>
              <Bot className="h-4 w-4" />
              <AlertDescription>
                OpenAI API key is configured as a Supabase secret. Test the connection below to verify it's working correctly.
              </AlertDescription>
            </Alert>
          </CardContent>
        </Card>

        {/* Connection Test */}
        <Card>
          <CardHeader>
            <CardTitle>Connection Test</CardTitle>
            <CardDescription>
              Test the OpenAI API connection with a custom prompt
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="test-prompt">Test Prompt</Label>
              <Textarea
                id="test-prompt"
                value={testPrompt}
                onChange={(e) => setTestPrompt(e.target.value)}
                placeholder="Enter a test prompt for OpenAI..."
                className="min-h-20"
              />
            </div>

            <Button onClick={testOpenAIConnection} disabled={testing} className="w-full">
              {testing ? (
                <>
                  <Activity className="mr-2 h-4 w-4 animate-spin" />
                  Testing Connection...
                </>
              ) : (
                <>
                  <TestTube className="mr-2 h-4 w-4" />
                  Test OpenAI Connection
                </>
              )}
            </Button>

            {testResponse && (
              <div className="space-y-2">
                <Label>Response</Label>
                <div className="bg-muted p-4 rounded-lg">
                  <pre className="text-sm whitespace-pre-wrap overflow-x-auto">
                    {testResponse}
                  </pre>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Usage Monitoring */}
        <Card>
          <CardHeader>
            <CardTitle>Usage Monitoring</CardTitle>
            <CardDescription>
              Monitor OpenAI API usage and costs
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-center py-8 text-muted-foreground">
              Usage monitoring dashboard coming soon...
              <br />
              <small>Integrate with OpenAI usage API for detailed analytics</small>
            </div>
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  );
};

export default OpenAIIntegration;