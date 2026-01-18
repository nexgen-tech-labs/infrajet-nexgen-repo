import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { X, Cookie, Settings } from 'lucide-react';
import { Link } from 'react-router-dom';

const CookieBanner = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    const cookieConsent = localStorage.getItem('cookieConsent');
    if (!cookieConsent) {
      setIsVisible(true);
    }
  }, []);

  const handleAcceptAll = () => {
    localStorage.setItem('cookieConsent', 'accepted');
    setIsVisible(false);
  };

  const handleRejectAll = () => {
    localStorage.setItem('cookieConsent', 'rejected');
    setIsVisible(false);
  };

  const handleDismiss = () => {
    setIsVisible(false);
  };

  if (!isVisible) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 p-4 sm:p-6">
      <Card className="mx-auto max-w-4xl bg-card/95 backdrop-blur-sm border-border shadow-lg">
        <div className="p-4 sm:p-6">
          <div className="flex items-start gap-3 mb-4">
            <Cookie className="h-6 w-6 text-primary flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <h3 className="text-lg font-semibold text-card-foreground mb-2">
                We use cookies
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                We use cookies and similar technologies to enhance your browsing experience, 
                analyze site traffic, and personalize content. By clicking "Accept All", 
                you consent to our use of cookies.
              </p>
              
              {isExpanded && (
                <div className="mt-4 text-sm text-muted-foreground space-y-2">
                  <p><strong>Essential cookies:</strong> Required for basic site functionality</p>
                  <p><strong>Analytics cookies:</strong> Help us understand how you use our site</p>
                  <p><strong>Marketing cookies:</strong> Used to show you relevant advertisements</p>
                </div>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDismiss}
              className="text-muted-foreground hover:text-card-foreground flex-shrink-0"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
            <div className="flex flex-col sm:flex-row gap-2 order-2 sm:order-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsExpanded(!isExpanded)}
                className="text-muted-foreground hover:text-card-foreground"
              >
                <Settings className="h-4 w-4 mr-2" />
                {isExpanded ? 'Less info' : 'More info'}
              </Button>
              <Link to="/cookies">
                <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-card-foreground">
                  Cookie Policy
                </Button>
              </Link>
            </div>

            <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto order-1 sm:order-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRejectAll}
                className="w-full sm:w-auto"
              >
                Decline
              </Button>
              <Button
                onClick={handleAcceptAll}
                size="sm"
                className="w-full sm:w-auto"
              >
                Accept All
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default CookieBanner;