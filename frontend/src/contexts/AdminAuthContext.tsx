import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { supabase } from '@/integrations/supabase/client';

interface AdminUser {
  id: string;
  email: string;
  full_name: string | null;
  role: 'super_admin' | 'admin' | 'moderator';
  is_active: boolean;
}

interface AdminAuthContextType {
  adminUser: AdminUser | null;
  signIn: (email: string, password: string) => Promise<{ error: any }>;
  signOut: () => Promise<void>;
  loading: boolean;
}

const AdminAuthContext = createContext<AdminAuthContextType | undefined>(undefined);

export const useAdminAuth = () => {
  const context = useContext(AdminAuthContext);
  if (context === undefined) {
    throw new Error('useAdminAuth must be used within an AdminAuthProvider');
  }
  return context;
};

interface AdminAuthProviderProps {
  children: ReactNode;
}

export const AdminAuthProvider = ({ children }: AdminAuthProviderProps) => {
  const [adminUser, setAdminUser] = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkAdminSession = async () => {
      try {
        const storedToken = localStorage.getItem('admin_access_token');
        if (storedToken) {
          // Verify token with backend
          const { data, error } = await supabase.functions.invoke('admin-auth', {
            body: { action: 'verify' },
            headers: {
              Authorization: `Bearer ${storedToken}`
            }
          });

          if (error || !data?.user) {
            localStorage.removeItem('admin_access_token');
            localStorage.removeItem('admin_refresh_token');
          } else {
            setAdminUser(data.user);
          }
        }
      } catch (error) {
        console.error('Error checking admin session:', error);
        localStorage.removeItem('admin_access_token');
        localStorage.removeItem('admin_refresh_token');
      } finally {
        setLoading(false);
      }
    };

    checkAdminSession();
  }, []);

  const signIn = async (email: string, password: string) => {
    try {
      const { data, error } = await supabase.functions.invoke('admin-auth', {
        body: {
          email,
          password,
          action: 'login'
        }
      });

      if (error) {
        console.error('Admin login error:', error);
        return { error: { message: 'Authentication failed' } };
      }

      if (data?.error) {
        return { error: { message: data.error } };
      }

      if (data?.user && data?.session) {
        setAdminUser(data.user);
        
        // Store secure tokens
        localStorage.setItem('admin_access_token', data.session.access_token);
        if (data.session.refresh_token) {
          localStorage.setItem('admin_refresh_token', data.session.refresh_token);
        }

        return { error: null };
      }

      return { error: { message: 'Authentication failed' } };
    } catch (error) {
      console.error('Admin login error:', error);
      return { error: { message: 'Authentication failed' } };
    }
  };

  const signOut = async () => {
    localStorage.removeItem('admin_access_token');
    localStorage.removeItem('admin_refresh_token');
    setAdminUser(null);
  };

  const value = {
    adminUser,
    signIn,
    signOut,
    loading,
  };

  return (
    <AdminAuthContext.Provider value={value}>
      {children}
    </AdminAuthContext.Provider>
  );
};