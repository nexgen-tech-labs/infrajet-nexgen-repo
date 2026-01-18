import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const Enterprise = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted">
      <Header />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent mb-6">
            Enterprise Solutions
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Scale your infrastructure automation across your entire organization with 
            enterprise-grade security, compliance, and dedicated support.
          </p>
        </div>

        {/* Key Features */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 mb-16">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                🏢 On-Premise Deployment
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Deploy infraJet within your own infrastructure for maximum security 
                and compliance with your data governance policies.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                🔐 Advanced Security
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                SOC 2 Type II compliance, role-based access control, audit logs, 
                and enterprise-grade encryption at rest and in transit.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                🔗 SSO Integration
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Seamless integration with your existing identity providers including 
                SAML, LDAP, Active Directory, and OAuth providers.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                📊 Advanced Analytics
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Comprehensive usage analytics, cost optimization insights, and 
                infrastructure performance metrics across your organization.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                🎯 Custom Workflows
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Build custom approval workflows, automated compliance checks, 
                and integration with your existing DevOps toolchain.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                🚀 Dedicated Support
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                24/7 dedicated support team, custom SLA agreements, and direct 
                access to our engineering team for technical guidance.
              </CardDescription>
            </CardContent>
          </Card>
        </div>

        {/* Enterprise Benefits */}
        <div className="bg-muted/50 p-8 rounded-lg mb-16">
          <h2 className="text-3xl font-bold text-center mb-8">Why Enterprises Choose infraJet</h2>
          <div className="grid md:grid-cols-2 gap-8">
            <div>
              <h3 className="text-xl font-semibold mb-4">Scale with Confidence</h3>
              <ul className="space-y-2 text-muted-foreground">
                <li>• Support for thousands of concurrent users</li>
                <li>• Multi-region deployment capabilities</li>
                <li>• High availability and disaster recovery</li>
                <li>• Performance monitoring and optimization</li>
              </ul>
            </div>
            <div>
              <h3 className="text-xl font-semibold mb-4">Enterprise Compliance</h3>
              <ul className="space-y-2 text-muted-foreground">
                <li>• SOC 2 Type II certified</li>
                <li>• GDPR and CCPA compliant</li>
                <li>• ISO 27001 security standards</li>
                <li>• Regular third-party security audits</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Success Stories */}
        <div className="mb-16">
          <h2 className="text-3xl font-bold text-center mb-8">Success Stories</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <Card>
              <CardHeader>
                <CardTitle>Fortune 500 Financial Services</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>
                  "infraJet helped us reduce infrastructure deployment time by 75% 
                  while maintaining strict compliance requirements."
                </CardDescription>
                <div className="mt-4 text-sm font-medium">- CTO, Major Bank</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Global Technology Company</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>
                  "The enterprise features allowed us to standardize infrastructure 
                  across 15+ development teams with centralized governance."
                </CardDescription>
                <div className="mt-4 text-sm font-medium">- VP Engineering</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Healthcare Organization</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>
                  "HIPAA compliance was seamless with infraJet's enterprise security 
                  features and audit capabilities."
                </CardDescription>
                <div className="mt-4 text-sm font-medium">- DevOps Director</div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Contact Section */}
        <div className="text-center bg-primary/5 p-8 rounded-lg">
          <h2 className="text-3xl font-bold mb-4">Ready to Transform Your Infrastructure?</h2>
          <p className="text-muted-foreground mb-6 max-w-2xl mx-auto">
            Schedule a demo with our enterprise team to see how infraJet can scale 
            with your organization's needs.
          </p>
          <div className="flex gap-4 justify-center">
            <Button size="lg">
              Schedule Demo
            </Button>
            <Button variant="outline" size="lg">
              Contact Sales
            </Button>
            <Button variant="outline" size="lg">
              Request Pricing
            </Button>
          </div>
        </div>
      </main>
      
      <Footer />
    </div>
  );
};

export default Enterprise;