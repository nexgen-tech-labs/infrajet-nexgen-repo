import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const Support = () => {
  const supportOptions = [
    {
      title: "Documentation",
      description: "Find answers in our comprehensive documentation",
      action: "Browse Docs",
      availability: "24/7"
    },
    {
      title: "Community Forum",
      description: "Get help from our community of developers",
      action: "Join Forum",
      availability: "Community-driven"
    },
    {
      title: "Email Support",
      description: "Send us an email for technical assistance",
      action: "Send Email",
      availability: "Business hours"
    },
    {
      title: "Priority Support",
      description: "Direct access to our engineering team",
      action: "Contact Sales",
      availability: "Enterprise only"
    }
  ];

  const faqItems = [
    {
      question: "How do I get started with InfraJet?",
      answer: "Check out our Getting Started guide in the documentation section."
    },
    {
      question: "What cloud providers do you support?",
      answer: "We support AWS, Azure, Google Cloud, and Kubernetes deployments."
    },
    {
      question: "Is there a free tier available?",
      answer: "Yes! We offer a free tier with generous limits for personal projects."
    },
    {
      question: "How can I upgrade my subscription?",
      answer: "You can upgrade your plan from your account dashboard or contact sales."
    }
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 bg-gradient-to-br from-background to-muted/20">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-6xl mx-auto space-y-8">
            <div className="text-center space-y-4">
              <h1 className="text-4xl font-bold tracking-tight">Support Center</h1>
              <p className="text-xl text-muted-foreground">
                Get the help you need, when you need it
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              {supportOptions.map((option, index) => (
                <Card key={index}>
                  <CardHeader>
                    <CardTitle className="text-lg">{option.title}</CardTitle>
                    <Badge variant="outline" className="w-fit">{option.availability}</Badge>
                  </CardHeader>
                  <CardContent>
                    <p className="text-muted-foreground mb-4">{option.description}</p>
                    <Button variant="outline" className="w-full">{option.action}</Button>
                  </CardContent>
                </Card>
              ))}
            </div>

            <div className="grid gap-8 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Submit a Support Ticket</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="support-email">Email</Label>
                    <Input id="support-email" type="email" placeholder="your@email.com" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="priority">Priority</Label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="Select priority" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="low">Low</SelectItem>
                        <SelectItem value="medium">Medium</SelectItem>
                        <SelectItem value="high">High</SelectItem>
                        <SelectItem value="urgent">Urgent</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="category">Category</Label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="Select category" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="technical">Technical Issue</SelectItem>
                        <SelectItem value="billing">Billing</SelectItem>
                        <SelectItem value="feature">Feature Request</SelectItem>
                        <SelectItem value="bug">Bug Report</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="subject">Subject</Label>
                    <Input id="subject" placeholder="Brief description of your issue" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="description">Description</Label>
                    <Textarea 
                      id="description" 
                      placeholder="Provide detailed information about your issue..."
                      className="min-h-[120px]"
                    />
                  </div>
                  <Button className="w-full">Submit Ticket</Button>
                </CardContent>
              </Card>

              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Frequently Asked Questions</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {faqItems.map((item, index) => (
                      <div key={index} className="border-b last:border-b-0 pb-4 last:pb-0">
                        <h3 className="font-semibold mb-2">{item.question}</h3>
                        <p className="text-muted-foreground text-sm">{item.answer}</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>System Status</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="flex justify-between items-center">
                        <span>API Services</span>
                        <Badge className="bg-green-500">Operational</Badge>
                      </div>
                      <div className="flex justify-between items-center">
                        <span>Web Application</span>
                        <Badge className="bg-green-500">Operational</Badge>
                      </div>
                      <div className="flex justify-between items-center">
                        <span>GitHub Integration</span>
                        <Badge className="bg-green-500">Operational</Badge>
                      </div>
                      <div className="flex justify-between items-center">
                        <span>Cloud Deployments</span>
                        <Badge className="bg-green-500">Operational</Badge>
                      </div>
                    </div>
                    <Button variant="outline" className="w-full mt-4">
                      View Status Page
                    </Button>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Support;