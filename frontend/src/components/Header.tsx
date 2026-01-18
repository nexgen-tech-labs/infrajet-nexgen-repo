import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import UserMenu from "./UserMenu";
import { Button } from "@/components/ui/button";
const Header = () => {
  const { user } = useAuth();

  return (
    <header className="glass-effect border-b border-border sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between min-h-[4rem]">
          {/* Logo - Following Law of Proximity */}
          <div className="flex items-center space-x-3">
            <Link to="/" className="flex items-center space-x-0 hover:opacity-80 transition-opacity duration-normal">
              <span className="sr-only">InfraJet</span>
              <img
                src="/brand-logo.svg"
                alt="InfraJet logo"
                className="h-10 w-auto md:h-12"
                loading="lazy"
              />
            </Link>
          </div>

          {/* Navigation - Reduced choices (Hick's Law) */}
          <nav className="hidden md:flex items-center space-x-1">
            {user && (
              <>
                <Link
                  to="/projects"
                  className="px-4 py-2 text-sm font-medium text-foreground-secondary hover:text-foreground hover:bg-secondary-hover rounded-lg transition-all duration-normal"
                >
                  Projects
                </Link>
                
              </>
            )}
            <Link
              to="/product"
              className="px-4 py-2 text-sm font-medium text-foreground-secondary hover:text-foreground hover:bg-secondary-hover rounded-lg transition-all duration-normal"
            >
              Product
            </Link>
            <Link
              to="/pricing"
              className="px-4 py-2 text-sm font-medium text-foreground-secondary hover:text-foreground hover:bg-secondary-hover rounded-lg transition-all duration-normal"
            >
              Pricing
            </Link>
            <Link
              to="/resources"
              className="px-4 py-2 text-sm font-medium text-foreground-secondary hover:text-foreground hover:bg-secondary-hover rounded-lg transition-all duration-normal"
            >
              Resources
            </Link>
           
          </nav>

          {/* CTA - Fitts' Law compliance */}
          <div className="flex items-center">
            {user ? (
              <UserMenu />
            ) : (
              <Link to="/auth">
                <Button variant="default" size="default" className="font-medium">
                  Get Started
                </Button>
              </Link>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
export default Header;