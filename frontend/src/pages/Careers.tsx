import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const Careers = () => {
  const openPositions = [
    {
      title: "Senior Full Stack Developer",
      department: "Engineering",
      location: "Remote",
      type: "Full-time"
    },
    {
      title: "DevOps Engineer",
      department: "Infrastructure",
      location: "San Francisco, CA",
      type: "Full-time"
    },
    {
      title: "Product Designer",
      department: "Design",
      location: "Remote",
      type: "Full-time"
    }
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 bg-gradient-to-br from-background to-muted/20">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-4xl mx-auto space-y-8">
            <div className="text-center space-y-4">
              <h1 className="text-4xl font-bold tracking-tight">Join Our Team</h1>
              <p className="text-xl text-muted-foreground">
                We will come back soon to start recruitment as we are still building our Team.
              </p>
            </div>

            {/* <Card>
              <CardHeader>
                <CardTitle>Why Work With Us?</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <h3 className="font-semibold mb-2">🚀 Cutting-edge Technology</h3>
                    <p className="text-sm text-muted-foreground">
                      Work with the latest technologies in AI, cloud infrastructure, and automation
                    </p>
                  </div>
                  <div>
                    <h3 className="font-semibold mb-2">🌍 Remote-first Culture</h3>
                    <p className="text-sm text-muted-foreground">
                      Flexible work arrangements with a focus on work-life balance
                    </p>
                  </div>
                  <div>
                    <h3 className="font-semibold mb-2">📈 Growth Opportunities</h3>
                    <p className="text-sm text-muted-foreground">
                      Continuous learning and career development opportunities
                    </p>
                  </div>
                  <div>
                    <h3 className="font-semibold mb-2">💡 Impact-driven Work</h3>
                    <p className="text-sm text-muted-foreground">
                      Build products that make a real difference for developers worldwide
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="space-y-4">
              <h2 className="text-2xl font-bold">Open Positions</h2>
              <div className="space-y-4">
                {openPositions.map((position, index) => (
                  <Card key={index}>
                    <CardContent className="p-6">
                      <div className="flex justify-between items-start">
                        <div className="space-y-2">
                          <h3 className="text-lg font-semibold">{position.title}</h3>
                          <div className="flex gap-2">
                            <Badge variant="secondary">{position.department}</Badge>
                            <Badge variant="outline">{position.location}</Badge>
                            <Badge variant="outline">{position.type}</Badge>
                          </div>
                        </div>
                        <Button>Apply Now</Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div> */}

            {/* <Card>
              <CardContent className="p-6 text-center">
                <h3 className="text-lg font-semibold mb-2">Don't see a perfect fit?</h3>
                <p className="text-muted-foreground mb-4">
                  We're always looking for talented individuals to join our team. Send us your resume!
                </p>
                <Button>Send Resume</Button>
              </CardContent>
            </Card> */}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Careers;