import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Users,
  CreditCard,
  AlertTriangle,
  Ticket,
  Bot,
  Settings,
  BarChart3,
  LogOut,
  Menu,
  X,
  ArrowLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAdminAuth } from "@/contexts/AdminAuthContext";

const adminNavItems = [
  { title: "Dashboard", url: "/admin", icon: BarChart3 },
  { title: "User Management", url: "/admin/users", icon: Users },
  { title: "Subscription Management", url: "/admin/subscriptions", icon: CreditCard },
  { title: "System Alerts", url: "/admin/alerts", icon: AlertTriangle },
  { title: "Promo Codes", url: "/admin/promo-codes", icon: Ticket },
  { title: "OpenAI Integration", url: "/admin/openai", icon: Bot },
  { title: "System Configuration", url: "/admin/config", icon: Settings },
];

export function AdminSidebar() {
  const { adminUser, signOut } = useAdminAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const isActive = (path: string) => {
    if (path === "/admin") {
      return location.pathname === "/admin";
    }
    return location.pathname.startsWith(path);
  };

  const getNavClassName = (isActive: boolean) =>
    `flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive
        ? "bg-primary text-primary-foreground"
        : "text-muted-foreground hover:text-foreground hover:bg-muted"
    }`;

  return (
    <div className={`bg-card border-r border-border transition-all duration-300 ${
      collapsed ? "w-16" : "w-64"
    }`}>
      <div className="flex h-full flex-col">
        {/* Header */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-border">
          {!collapsed && (
            <h2 className="text-lg font-semibold text-foreground">Admin Panel</h2>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCollapsed(!collapsed)}
            className="h-8 w-8 p-0"
          >
            {collapsed ? <Menu className="h-4 w-4" /> : <X className="h-4 w-4" />}
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 p-4">
          {/* Back to Dashboard Link */}
          <NavLink
            to="/"
            className="flex items-center px-3 py-2 rounded-lg text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            {!collapsed && <span>Back to Dashboard</span>}
          </NavLink>

          {adminNavItems.map((item) => (
            <NavLink
              key={item.title}
              to={item.url}
              end={item.url === "/admin"}
              className={({ isActive }) => getNavClassName(isActive)}
            >
              <item.icon className="h-4 w-4 mr-2 flex-shrink-0" />
              {!collapsed && <span>{item.title}</span>}
            </NavLink>
          ))}
        </nav>

        {/* User Info & Logout */}
        <div className="border-t border-border p-4">
          {!collapsed && adminUser && (
            <div className="mb-3 text-xs text-muted-foreground">
              <div className="font-medium text-foreground">{adminUser.full_name}</div>
              <div>{adminUser.email}</div>
              <div className="capitalize">{adminUser.role.replace('_', ' ')}</div>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={signOut}
            className="w-full justify-start text-muted-foreground hover:text-foreground"
          >
            <LogOut className="h-4 w-4 mr-2" />
            {!collapsed && <span>Sign out</span>}
          </Button>
        </div>
      </div>
    </div>
  );
}