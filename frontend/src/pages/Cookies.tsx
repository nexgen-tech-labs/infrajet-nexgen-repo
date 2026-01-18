import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const Cookies = () => {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-4xl">
        <div className="mb-6">
          <Link to="/auth">
            <Button variant="outline" className="mb-4">
              ← Back to Login
            </Button>
          </Link>
        </div>
        
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl font-bold">Cookie Policy</CardTitle>
            <CardDescription>
              Last updated: January 1, 2025
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <section>
              <h2 className="text-lg font-semibold mb-2">What Are Cookies</h2>
              <p className="text-muted-foreground">
                Cookies are small text files that are stored on your computer or mobile device when you visit our website. They are widely used to make websites work more efficiently and to provide information to site owners.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">How We Use Cookies</h2>
              <p className="text-muted-foreground mb-3">
                We use cookies for several purposes:
              </p>
              <ul className="list-disc pl-6 text-muted-foreground space-y-2">
                <li><strong>Essential Cookies:</strong> Required for the website to function properly, including authentication and security features.</li>
                <li><strong>Performance Cookies:</strong> Help us understand how visitors interact with our website by collecting anonymous information.</li>
                <li><strong>Functionality Cookies:</strong> Remember your preferences and settings to enhance your user experience.</li>
                <li><strong>Analytics Cookies:</strong> Help us analyze website traffic and optimize our services.</li>
              </ul>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Types of Cookies We Use</h2>
              <div className="space-y-3">
                <div>
                  <h3 className="font-medium text-foreground">Session Cookies</h3>
                  <p className="text-muted-foreground text-sm">Temporary cookies that are deleted when you close your browser.</p>
                </div>
                <div>
                  <h3 className="font-medium text-foreground">Persistent Cookies</h3>
                  <p className="text-muted-foreground text-sm">Cookies that remain on your device until they expire or are manually deleted.</p>
                </div>
                <div>
                  <h3 className="font-medium text-foreground">Third-Party Cookies</h3>
                  <p className="text-muted-foreground text-sm">Cookies set by external services we use, such as analytics providers.</p>
                </div>
              </div>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Managing Cookies</h2>
              <p className="text-muted-foreground mb-3">
                You can control and manage cookies in several ways:
              </p>
              <ul className="list-disc pl-6 text-muted-foreground space-y-2">
                <li>Use your browser settings to block or delete cookies</li>
                <li>Set your browser to notify you when cookies are being sent</li>
                <li>Use browser extensions or privacy tools</li>
                <li>Opt out of third-party analytics services</li>
              </ul>
              <p className="text-muted-foreground mt-3">
                Please note that disabling certain cookies may affect the functionality of our website.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Third-Party Services</h2>
              <p className="text-muted-foreground">
                We may use third-party services that place cookies on your device. These services include analytics providers, authentication services, and other tools that help us improve our website. Each third-party service has its own cookie policy.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Updates to This Policy</h2>
              <p className="text-muted-foreground">
                We may update this Cookie Policy from time to time to reflect changes in our practices or applicable laws. We will notify you of any material changes by posting the updated policy on our website.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold mb-2">Contact Information</h2>
              <p className="text-muted-foreground">
                If you have questions about our use of cookies, please contact us at:
              </p>
              <div className="mt-2 text-muted-foreground">
                <p>Email: privacy@infrajet.com</p>
                <p>Address: [Your Company Address]</p>
              </div>
            </section>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Cookies;