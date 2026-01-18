import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const Pricing = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted">
      <Header />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent mb-6">
            Simple, Transparent Pricing
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Choose the plan that fits your team size and infrastructure needs. 
            All plans include unlimited deployments and 24/7 support.
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-3 gap-8 mb-16">
          {/* Starter Plan */}
          <Card className="relative">
            <CardHeader className="text-center">
              <CardTitle className="text-2xl">Starter</CardTitle>
              <CardDescription>Perfect for individuals and small projects</CardDescription>
              <div className="mt-4">
                <span className="text-4xl font-bold">$0</span>
                <span className="text-muted-foreground">/month</span>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <ul className="space-y-2 text-sm">
                <li className="flex items-center gap-2">
                  ✓ Up to 3 projects
                </li>
                <li className="flex items-center gap-2">
                  ✓ 50 AI generations/month
                </li>
                <li className="flex items-center gap-2">
                  ✓ Basic templates
                </li>
                <li className="flex items-center gap-2">
                  ✓ Community support
                </li>
                <li className="flex items-center gap-2">
                  ✓ GitHub integration
                </li>
              </ul>
              <Button className="w-full" variant="outline">
                Get Started Free
              </Button>
            </CardContent>
          </Card>

          {/* Pro Plan */}
          <Card className="relative border-primary">
            <Badge className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-primary">
              Most Popular
            </Badge>
            <CardHeader className="text-center">
              <CardTitle className="text-2xl">Professional</CardTitle>
              <CardDescription>For growing teams and production workloads</CardDescription>
              <div className="mt-4">
                <span className="text-4xl font-bold">$29</span>
                <span className="text-muted-foreground">/month</span>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <ul className="space-y-2 text-sm">
                <li className="flex items-center gap-2">
                  ✓ Unlimited projects
                </li>
                <li className="flex items-center gap-2">
                  ✓ 500 AI generations/month
                </li>
                <li className="flex items-center gap-2">
                  ✓ Premium templates
                </li>
                <li className="flex items-center gap-2">
                  ✓ Priority support
                </li>
                <li className="flex items-center gap-2">
                  ✓ Advanced security scanning
                </li>
                <li className="flex items-center gap-2">
                  ✓ Team collaboration
                </li>
                <li className="flex items-center gap-2">
                  ✓ Custom integrations
                </li>
              </ul>
              <Button className="w-full">
                Start Pro Trial
              </Button>
            </CardContent>
          </Card>

          {/* Enterprise Plan */}
          <Card className="relative">
            <CardHeader className="text-center">
              <CardTitle className="text-2xl">Enterprise</CardTitle>
              <CardDescription>For large organizations with custom needs</CardDescription>
              <div className="mt-4">
                <span className="text-4xl font-bold">Custom</span>
                <span className="text-muted-foreground">/month</span>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <ul className="space-y-2 text-sm">
                <li className="flex items-center gap-2">
                  ✓ Everything in Pro
                </li>
                <li className="flex items-center gap-2">
                  ✓ Unlimited AI generations
                </li>
                <li className="flex items-center gap-2">
                  ✓ Custom templates
                </li>
                <li className="flex items-center gap-2">
                  ✓ Dedicated support
                </li>
                <li className="flex items-center gap-2">
                  ✓ On-premise deployment
                </li>
                <li className="flex items-center gap-2">
                  ✓ SSO integration
                </li>
                <li className="flex items-center gap-2">
                  ✓ Custom SLA
                </li>
              </ul>
              <Button className="w-full" variant="outline">
                Contact Sales
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* FAQ Section */}
        <div className="text-center">
          <h2 className="text-3xl font-bold mb-8">Frequently Asked Questions</h2>
          <div className="grid md:grid-cols-2 gap-8 text-left max-w-4xl mx-auto">
            <div>
              <h3 className="font-semibold mb-2">Can I change plans anytime?</h3>
              <p className="text-muted-foreground text-sm">
                Yes, you can upgrade or downgrade your plan at any time. Changes will be reflected in your next billing cycle.
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Is there a free trial?</h3>
              <p className="text-muted-foreground text-sm">
                Yes, all paid plans come with a 14-day free trial. No credit card required to start.
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">What payment methods do you accept?</h3>
              <p className="text-muted-foreground text-sm">
                We accept all major credit cards, PayPal, and wire transfers for enterprise customers.
              </p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Do you offer refunds?</h3>
              <p className="text-muted-foreground text-sm">
                Yes, we offer a 30-day money-back guarantee for all new subscriptions.
              </p>
            </div>
          </div>
        </div>
      </main>
      
      <Footer />
    </div>
  );
};

export default Pricing;