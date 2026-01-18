import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const Resources = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted">
      <Header />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent mb-6">
            Resources & Documentation
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Everything you need to master infrastructure as code with comprehensive 
            guides, tutorials, and best practices.
          </p>
        </div>

        {/* Resource Categories */}
        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                📚 Documentation
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h4 className="font-semibold mb-2">Getting Started Guide</h4>
                <CardDescription>Complete walkthrough for new users</CardDescription>
              </div>
              <div>
                <h4 className="font-semibold mb-2">API Reference</h4>
                <CardDescription>Comprehensive API documentation</CardDescription>
              </div>
              <div>
                <h4 className="font-semibold mb-2">CLI Documentation</h4>
                <CardDescription>Command line interface reference</CardDescription>
              </div>
              <Button variant="outline" className="w-full">
                Browse Documentation
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                🎓 Tutorials
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h4 className="font-semibold mb-2">Terraform Basics</h4>
                <CardDescription>Learn infrastructure as code fundamentals</CardDescription>
              </div>
              <div>
                <h4 className="font-semibold mb-2">AWS Deployment</h4>
                <CardDescription>Deploy to Amazon Web Services</CardDescription>
              </div>
              <div>
                <h4 className="font-semibold mb-2">Kubernetes Setup</h4>
                <CardDescription>Container orchestration made simple</CardDescription>
              </div>
              <Button variant="outline" className="w-full">
                Start Learning
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                💡 Best Practices
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h4 className="font-semibold mb-2">Security Guidelines</h4>
                <CardDescription>Secure your infrastructure deployments</CardDescription>
              </div>
              <div>
                <h4 className="font-semibold mb-2">Performance Optimization</h4>
                <CardDescription>Optimize costs and performance</CardDescription>
              </div>
              <div>
                <h4 className="font-semibold mb-2">Team Collaboration</h4>
                <CardDescription>Workflows for development teams</CardDescription>
              </div>
              <Button variant="outline" className="w-full">
                View Guidelines
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                🛠️ Tools & Templates
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h4 className="font-semibold mb-2">Starter Templates</h4>
                <CardDescription>Pre-built infrastructure templates</CardDescription>
              </div>
              <div>
                <h4 className="font-semibold mb-2">Code Examples</h4>
                <CardDescription>Real-world configuration examples</CardDescription>
              </div>
              <div>
                <h4 className="font-semibold mb-2">Integration Tools</h4>
                <CardDescription>Connect with your existing tools</CardDescription>
              </div>
              <Button variant="outline" className="w-full">
                Download Resources
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Community Section */}
        <div className="text-center bg-muted/50 p-8 rounded-lg">
          <h2 className="text-3xl font-bold mb-4">Join Our Community</h2>
          <p className="text-muted-foreground mb-6 max-w-2xl mx-auto">
            Connect with other developers, ask questions, and share your infrastructure 
            automation success stories.
          </p>
          <div className="flex gap-4 justify-center">
            <Button>Join Discord</Button>
            <Button variant="outline">GitHub Discussions</Button>
            <Button variant="outline">Stack Overflow</Button>
          </div>
        </div>
      </main>
      
      <Footer />
    </div>
  );
};

export default Resources;