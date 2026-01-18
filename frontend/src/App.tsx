import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import CookieBanner from "@/components/CookieBanner";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { AdminAuthProvider } from "@/contexts/AdminAuthContext";
import { GitHubProvider } from "@/contexts/GitHubContext";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import AuthGuard from "@/components/AuthGuard";
import AdminAuthGuard from "@/components/admin/AdminAuthGuard";
import Index from "./pages/Index";
import Auth from "./pages/Auth";
import Landing from "./pages/Landing";
import { Projects } from "./pages/Projects";
import ProjectManagement from "./pages/ProjectManagement";
import Product from "./pages/Product";
import Resources from "./pages/Resources";
import Pricing from "./pages/Pricing";
import Enterprise from "./pages/Enterprise";
import About from "./pages/About";
import Careers from "./pages/Careers";
import Contact from "./pages/Contact";
import Documentation from "./pages/Documentation";
import Features from "./pages/Features";
import Blog from "./pages/Blog";
import Community from "./pages/Community";
import Support from "./pages/Support";
import Terms from "./pages/Terms";
import Privacy from "./pages/Privacy";
import Cookies from "./pages/Cookies";
import NotFound from "./pages/NotFound";
import GitHubCallback from "./pages/GitHubCallback";
import GitHubOAuthCallback from "./pages/GitHubOAuthCallback";
import Profile from "./pages/Profile";
import ChatDemo from "./pages/ChatDemo";
import AdminLogin from "./pages/admin/AdminLogin";
import AdminDashboard from "./pages/admin/AdminDashboard";
import UserManagement from "./pages/admin/UserManagement";
import SubscriptionManagement from "./pages/admin/SubscriptionManagement";
import SystemAlerts from "./pages/admin/SystemAlerts";
import PromoCodes from "./pages/admin/PromoCodes";
import OpenAIIntegration from "./pages/admin/OpenAIIntegration";
import SystemConfiguration from "./pages/admin/SystemConfiguration";
import { RuntimeConfig } from "./config";

const queryClient = new QueryClient();

interface AppProps {
  config: RuntimeConfig;
}

const App = ({ config }: AppProps) => (

  <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <GitHubProvider>
          <TooltipProvider>
            <Toaster />
            <Sonner />
            <BrowserRouter>
              <CookieBanner />
              <Routes>
                <Route path="/" element={<Landing />} />
                <Route path="/app" element={
                  <AuthGuard>
                    <Index />
                  </AuthGuard>
                } />
                <Route path="/projects" element={
                  <AuthGuard>
                    <Projects />
                  </AuthGuard>
                } />
                <Route path="/project-management" element={
                  <AuthGuard>
                    <ProjectManagement />
                  </AuthGuard>
                } />
                <Route path="/projects/:projectId" element={
                  <AuthGuard>
                    <ProjectManagement />
                  </AuthGuard>
                } />
                <Route path="/profile" element={
                  <AuthGuard>
                    <Profile />
                  </AuthGuard>
                } />
                <Route path="/chat" element={
                  <AuthGuard>
                    <ChatDemo />
                  </AuthGuard>
                } />
                <Route path="/chat-demo" element={
                  <AuthGuard>
                    <ChatDemo />
                  </AuthGuard>
                } />
                <Route path="/product" element={<Product />} />
                <Route path="/resources" element={<Resources />} />
                <Route path="/pricing" element={<Pricing />} />
                <Route path="/enterprise" element={<Enterprise />} />
                <Route path="/about" element={<About />} />
                <Route path="/careers" element={<Careers />} />
                <Route path="/contact" element={<Contact />} />
                <Route path="/documentation" element={<Documentation />} />
                <Route path="/docs" element={<Documentation />} />
                <Route path="/features" element={<Features />} />
                <Route path="/blog" element={<Blog />} />
                <Route path="/community" element={<Community />} />
                <Route path="/support" element={<Support />} />
                <Route path="/auth" element={<Auth />} />
                <Route path="/auth/github/callback" element={<GitHubCallback />} />
                <Route path="/auth/github/oauth/callback" element={<GitHubOAuthCallback />} />
                <Route path="/terms" element={<Terms />} />
                <Route path="/privacy" element={<Privacy />} />
                <Route path="/cookies" element={<Cookies />} />

                {/* Admin Routes */}
                <Route path="/admin/*" element={
                  <AdminAuthProvider>
                    <Routes>
                      <Route path="login" element={<AdminLogin />} />
                      <Route path="" element={
                        <AdminAuthGuard>
                          <AdminDashboard />
                        </AdminAuthGuard>
                      } />
                      <Route path="users" element={
                        <AdminAuthGuard>
                          <UserManagement />
                        </AdminAuthGuard>
                      } />
                      <Route path="subscriptions" element={
                        <AdminAuthGuard>
                          <SubscriptionManagement />
                        </AdminAuthGuard>
                      } />
                      <Route path="alerts" element={
                        <AdminAuthGuard>
                          <SystemAlerts />
                        </AdminAuthGuard>
                      } />
                      <Route path="promo-codes" element={
                        <AdminAuthGuard>
                          <PromoCodes />
                        </AdminAuthGuard>
                      } />
                      <Route path="openai" element={
                        <AdminAuthGuard>
                          <OpenAIIntegration />
                        </AdminAuthGuard>
                      } />
                      <Route path="config" element={
                        <AdminAuthGuard>
                          <SystemConfiguration />
                        </AdminAuthGuard>
                      } />
                    </Routes>
                  </AdminAuthProvider>
                } />

                <Route path="*" element={<NotFound />} />
              </Routes>
            </BrowserRouter>
          </TooltipProvider>
        </GitHubProvider>
      </AuthProvider>
    </QueryClientProvider>
  </ErrorBoundary>
);

export default App;
