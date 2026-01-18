import { useEffect, useState } from 'react';
import { AdminLayout } from '@/components/admin/AdminLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { supabase } from '@/integrations/supabase/client';
import { 
  Users, 
  CreditCard, 
  AlertTriangle, 
  Ticket, 
  Bot, 
  Settings,
  TrendingUp,
  Activity
} from 'lucide-react';
import { Link } from 'react-router-dom';

interface DashboardStats {
  totalUsers: number;
  activeSubscriptions: number;
  systemAlerts: number;
  activePromoCodes: number;
}

const AdminDashboard = () => {
  const [stats, setStats] = useState<DashboardStats>({
    totalUsers: 0,
    activeSubscriptions: 0,
    systemAlerts: 0,
    activePromoCodes: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        // Fetch user count
        const { count: userCount } = await supabase
          .from('profiles')
          .select('*', { count: 'exact', head: true });

        // Fetch active projects (representing subscriptions)
        const { count: subscriptionCount } = await supabase
          .from('projects')
          .select('*', { count: 'exact', head: true });

        // Fetch unresolved system alerts
        const { count: alertCount } = await supabase
          .from('system_alerts')
          .select('*', { count: 'exact', head: true })
          .eq('is_resolved', false);

        // Fetch active promo codes
        const { count: promoCount } = await supabase
          .from('promo_codes')
          .select('*', { count: 'exact', head: true })
          .eq('is_active', true);

        setStats({
          totalUsers: userCount || 0,
          activeSubscriptions: subscriptionCount || 0,
          systemAlerts: alertCount || 0,
          activePromoCodes: promoCount || 0,
        });
      } catch (error) {
        console.error('Error fetching dashboard stats:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  const quickActions = [
    {
      title: "User Management",
      description: "Manage user accounts and permissions",
      icon: Users,
      href: "/admin/users",
      color: "bg-blue-500"
    },
    {
      title: "Subscription Management",
      description: "Assign and manage user subscriptions",
      icon: CreditCard,
      href: "/admin/subscriptions",
      color: "bg-green-500"
    },
    {
      title: "System Alerts",
      description: "Monitor and resolve system issues",
      icon: AlertTriangle,
      href: "/admin/alerts",
      color: "bg-red-500",
      badge: stats.systemAlerts > 0 ? stats.systemAlerts : undefined
    },
    {
      title: "Promo Codes",
      description: "Create and manage promotional codes",
      icon: Ticket,
      href: "/admin/promo-codes",
      color: "bg-purple-500"
    },
    {
      title: "OpenAI Integration",
      description: "Test and monitor OpenAI connectivity",
      icon: Bot,
      href: "/admin/openai",
      color: "bg-orange-500"
    },
    {
      title: "System Configuration",
      description: "Manage global system settings",
      icon: Settings,
      href: "/admin/config",
      color: "bg-gray-500"
    }
  ];

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Admin Dashboard</h1>
          <p className="text-muted-foreground">
            Manage your SaaS platform from this central control panel
          </p>
        </div>

        {/* Stats Overview */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Users</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{loading ? '...' : stats.totalUsers}</div>
              <p className="text-xs text-muted-foreground">
                <TrendingUp className="inline h-3 w-3 mr-1" />
                All registered users
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Projects</CardTitle>
              <CreditCard className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{loading ? '...' : stats.activeSubscriptions}</div>
              <p className="text-xs text-muted-foreground">
                <Activity className="inline h-3 w-3 mr-1" />
                Current active projects
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">System Alerts</CardTitle>
              <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{loading ? '...' : stats.systemAlerts}</div>
              <p className="text-xs text-muted-foreground">
                Unresolved issues
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Promo Codes</CardTitle>
              <Ticket className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{loading ? '...' : stats.activePromoCodes}</div>
              <p className="text-xs text-muted-foreground">
                Currently available
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions */}
        <div>
          <h2 className="text-xl font-semibold mb-4 text-foreground">Quick Actions</h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {quickActions.map((action) => (
              <Card key={action.title} className="hover:shadow-md transition-shadow">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className={`p-2 rounded-lg ${action.color}`}>
                      <action.icon className="h-5 w-5 text-white" />
                    </div>
                    {action.badge && (
                      <Badge variant="destructive">{action.badge}</Badge>
                    )}
                  </div>
                  <CardTitle className="text-lg">{action.title}</CardTitle>
                  <CardDescription>{action.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <Button asChild className="w-full">
                    <Link to={action.href}>Manage</Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
};

export default AdminDashboard;