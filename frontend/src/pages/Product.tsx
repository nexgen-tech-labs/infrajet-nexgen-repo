import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const Product = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted">
      <Header />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent mb-6">
            Infrastructure as Code Platform
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Transform your infrastructure management with AI-powered code generation, 
            automated deployments, and enterprise-grade security.
          </p>
        </div>

        {/* Features Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 mb-16">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                🤖 AI-Powered Generation
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Generate Terraform, CloudFormation, and Kubernetes configurations 
                using natural language prompts powered by GPT-4.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                🔄 Multi-Cloud Support
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Deploy across AWS, Azure, GCP, and hybrid environments with 
                unified configuration management.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                🔒 Enterprise Security
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Built-in security scanning, compliance checks, and policy 
                enforcement for production-ready deployments.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                📊 Real-time Monitoring
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Monitor infrastructure health, costs, and performance with 
                integrated dashboards and alerting.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                🔀 GitOps Integration
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Seamless integration with GitHub, GitLab, and other version 
                control systems for automated workflows.
              </CardDescription>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                ⚡ Instant Deployment
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Deploy infrastructure changes in minutes, not hours, with 
                intelligent dependency management.
              </CardDescription>
            </CardContent>
          </Card>
        </div>

        {/* CTA Section */}
        <div className="text-center">
          <h2 className="text-3xl font-bold mb-6">Ready to Get Started?</h2>
          <div className="flex gap-4 justify-center">
            <Button size="lg" className="bg-primary hover:bg-primary/90">
              Start Free Trial
            </Button>
            <Button variant="outline" size="lg">
              Schedule Demo
            </Button>
          </div>
        </div>
      </main>
      
      <Footer />
    </div>
  );
};

export default Product;