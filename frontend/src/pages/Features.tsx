import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, Zap, Shield, Globe, Code, Database } from "lucide-react";

const Features = () => {
  const featureCategories = [
    // {
    //   title: "Core Infrastructure",
    //   icon: <Database className="h-6 w-6" />,
    //   features: [
    //     { name: "Auto-scaling", description: "Automatically scale your infrastructure based on demand" },
    //     { name: "Load Balancing", description: "Distribute traffic efficiently across your services" },
    //     { name: "Container Orchestration", description: "Manage containerized applications with ease" },
    //     { name: "Service Mesh", description: "Secure service-to-service communication" }
    //   ]
    // },
    {
      title: "Developer Experience",
      icon: <Code className="h-6 w-6" />,
      features: [
        { name: "Infrastructure as Code", description: "Define infrastructure using familiar code patterns" },
        { name: "GitOps Integration", description: "Deploy infrastructure changes through Git workflows" },
        { name: "Real-time Monitoring", description: "Monitor your infrastructure in real-time" },
        { name: "Automated Rollbacks", description: "Automatically rollback failed deployments" }
      ]
    },
    {
      title: "Security & Compliance",
      icon: <Shield className="h-6 w-6" />,
      features: [
        { name: "Zero Trust Architecture", description: "Secure by default with zero trust principles" },
        { name: "RBAC", description: "Role-based access control for team management" },
        { name: "Audit Logging", description: "Complete audit trail of all infrastructure changes" },
        { name: "Compliance Templates", description: "Pre-built templates for SOC2, HIPAA, and more" }
      ]
    },
    // {
    //   title: "Performance",
    //   icon: <Zap className="h-6 w-6" />,
    //   features: [
    //     { name: "Edge Computing", description: "Deploy closer to your users for better performance" },
    //     { name: "CDN Integration", description: "Built-in content delivery network" },
    //     { name: "Caching Layers", description: "Intelligent caching for improved response times" },
    //     { name: "Performance Analytics", description: "Detailed performance insights and recommendations" }
    //   ]
    // },
    {
      title: "Multi-Cloud",
      icon: <Globe className="h-6 w-6" />,
      features: [
        { name: "Cloud Agnostic", description: "Deploy to AWS, Azure, GCP, and more" },
        { name: "Multi-Region", description: "Deploy across multiple regions for high availability" },
        { name: "Cloud Migration", description: "Seamlessly migrate between cloud providers" },
        { name: "Cost Optimization", description: "Optimize costs across multiple cloud providers" }
      ]
    }
  ];

  const highlights = [
    "99.99% Uptime SLA",
    "Sub-second Deployments",
    "Enterprise Grade Security",
    "24/7 Support",
    "Global Edge Network",
    "Zero Downtime Updates"
  ];

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container mx-auto px-4 py-16">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent mb-6">
            Powerful Features
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto mb-8">
            Everything you need to build, deploy, and scale modern infrastructure with confidence.
          </p>
          
          {/* Highlights */}
          <div className="flex flex-wrap justify-center gap-3 mb-12">
            {highlights.map((highlight) => (
              <Badge key={highlight} variant="secondary" className="px-4 py-2">
                <CheckCircle className="h-4 w-4 mr-2" />
                {highlight}
              </Badge>
            ))}
          </div>
        </div>

        {/* Features Grid */}
        <div className="space-y-16">
          {featureCategories.map((category) => (
            <div key={category.title} className="space-y-8">
              <div className="text-center">
                <div className="flex items-center justify-center gap-3 mb-4">
                  {category.icon}
                  <h2 className="text-3xl font-bold">{category.title}</h2>
                </div>
              </div>
              
              <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                {category.features.map((feature) => (
                  <Card key={feature.name} className="border-border/50 hover:border-primary/50 transition-colors">
                    <CardHeader>
                      <CardTitle className="text-lg">{feature.name}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <CardDescription>{feature.description}</CardDescription>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Call to Action */}
        <div className="text-center mt-20">
          <Card className="max-w-4xl mx-auto bg-gradient-to-r from-primary/10 to-accent/10 border-primary/20">
            <CardContent className="pt-8 pb-8">
              <h3 className="text-2xl font-bold mb-4">Ready to Get Started?</h3>
              <p className="text-muted-foreground mb-6">
                Join thousands of developers who trust infraJet for their infrastructure needs.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <a 
                  href="/auth"
                  className="inline-flex items-center justify-center rounded-md bg-primary px-8 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  Start Free Trial
                </a>
                <a 
                  href="/documentation"
                  className="inline-flex items-center justify-center rounded-md border border-border px-8 py-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground transition-colors"
                >
                  View Documentation
                </a>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default Features;