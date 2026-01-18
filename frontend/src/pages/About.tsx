import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const About = () => {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 bg-gradient-to-br from-background to-muted/20">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-4xl mx-auto space-y-8">
            <div className="text-center space-y-4">
              <h1 className="text-4xl font-bold tracking-tight">About Us</h1>
              <p className="text-xl text-muted-foreground">
                Learn more about our mission, vision, and the team behind infraJet
              </p>
            </div>

            <div className="grid gap-8 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Our Mission</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">
                    We are dedicated to revolutionizing infrastructure management by making 
                    Infrastructure as Code accessible, intuitive, and powerful for teams of all sizes. 
                    Our AI-powered platform simplifies complex cloud deployments while maintaining 
                    enterprise-grade security and reliability.
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Our Vision</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">
                    To become the leading platform that democratizes cloud infrastructure management, 
                    enabling developers and organizations to focus on building amazing products 
                    rather than wrestling with complex deployment configurations.
                  </p>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Company Values</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="text-center">
                    <h3 className="font-semibold mb-2">Innovation</h3>
                    <p className="text-sm text-muted-foreground">
                      Continuously pushing the boundaries of what's possible in infrastructure automation
                    </p>
                  </div>
                  <div className="text-center">
                    <h3 className="font-semibold mb-2">Security</h3>
                    <p className="text-sm text-muted-foreground">
                      Maintaining the highest standards of security and compliance in everything we do
                    </p>
                  </div>
                  <div className="text-center">
                    <h3 className="font-semibold mb-2">Simplicity</h3>
                    <p className="text-sm text-muted-foreground">
                      Making complex infrastructure management simple and accessible to everyone
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default About;