import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";

const Documentation = () => {
  const docSections = [
    {
      title: "Getting Started",
      description: "Quick start guide and basic concepts",
      items: ["Installation", "First Project", "Basic Configuration", "Authentication"]
    },
    {
      title: "API Reference",
      description: "Complete API documentation",
      items: ["REST API", "GraphQL API", "Webhooks", "Rate Limits"]
    },
    {
      title: "Integrations",
      description: "Connect with your favorite tools",
      items: ["GitHub", "GitLab", "Jenkins", "Terraform"]
    },
    {
      title: "Deployment",
      description: "Deploy to various cloud providers",
      items: ["AWS", "Azure", "Google Cloud", "Kubernetes"]
    }
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 bg-gradient-to-br from-background to-muted/20">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-6xl mx-auto space-y-8">
            <div className="text-center space-y-4">
              <h1 className="text-4xl font-bold tracking-tight">Documentation</h1>
              <p className="text-xl text-muted-foreground">
                Everything you need to know about using infraJet
              </p>
            </div>

            <div className="max-w-md mx-auto">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                <Input 
                  placeholder="Search documentation..." 
                  className="pl-10"
                />
              </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              {docSections.map((section, index) => (
                <Card key={index}>
                  <CardHeader>
                    <CardTitle>{section.title}</CardTitle>
                    <p className="text-muted-foreground">{section.description}</p>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {section.items.map((item, itemIndex) => (
                        <Button 
                          key={itemIndex}
                          variant="ghost" 
                          className="w-full justify-start"
                        >
                          {item}
                        </Button>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            <div className="grid gap-6 md:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle>Tutorials</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground mb-4">
                    Step-by-step guides for common use cases
                  </p>
                  <Button variant="outline" className="w-full">View Tutorials</Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Examples</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground mb-4">
                    Code samples and project templates
                  </p>
                  <Button variant="outline" className="w-full">Browse Examples</Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>FAQ</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground mb-4">
                    Frequently asked questions and answers
                  </p>
                  <Button variant="outline" className="w-full">Read FAQ</Button>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Documentation;