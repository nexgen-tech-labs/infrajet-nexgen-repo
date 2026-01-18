import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const Community = () => {
  const communityStats = [
    { label: "Active Members", value: "100+" },
    { label: "GitHub Stars", value: " 500+" },
    { label: "Discord Members", value: "150+" },
    { label: "Contributions", value: "20+" }
  ];

  const communityChannels = [
    {
      name: "Discord Community",
      description: "Join our vibrant Discord server for real-time discussions, help, and networking",
      members: "100+ members",
      type: "Chat"
    },
    {
      name: "GitHub Discussions",
      description: "Technical discussions, feature requests, and collaborative problem-solving",
      members: "100+ contributors",
      type: "Development"
    },
    // {
    //   name: "Community Forum",
    //   description: "Long-form discussions, tutorials, and knowledge sharing",
    //   members: "12,000+ users",
    //   type: "Forum"
    // },
    // {
    //   name: "Stack Overflow",
    //   description: "Get help with specific technical questions and share solutions",
    //   members: "3,000+ questions",
    //   type: "Q&A"
    // }
  ];

  const upcomingEvents = [
    {
      title: "InfraJet Community Meetup",
      date: "November 15, 2025",
      time: "6:00 PM PST",
      type: "Virtual"
    },
    {
      title: "Infrastructure as Code Workshop",
      date: "December 5, 2025",
      time: "2:00 PM EST",
      type: "Online Workshop"
    },
    {
      title: "Monthly Contributors Call",
      date: "December 15, 2025",
      time: "10:00 AM PST",
      type: "Video Call"
    }
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 bg-gradient-to-br from-background to-muted/20">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-6xl mx-auto space-y-8">
            <div className="text-center space-y-4">
              <h1 className="text-4xl font-bold tracking-tight">Community</h1>
              <p className="text-xl text-muted-foreground">
                Join thousands of developers building the future of infrastructure automation
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
              {communityStats.map((stat, index) => (
                <Card key={index}>
                  <CardContent className="p-6 text-center">
                    <div className="text-2xl font-bold text-primary">{stat.value}</div>
                    <p className="text-muted-foreground">{stat.label}</p>
                  </CardContent>
                </Card>
              ))}
            </div>

            <div className="space-y-4">
              <h2 className="text-2xl font-bold">Join the Conversation</h2>
              <div className="grid gap-6 md:grid-cols-2">
                {communityChannels.map((channel, index) => (
                  <Card key={index}>
                    <CardHeader>
                      <div className="flex justify-between items-start">
                        <CardTitle>{channel.name}</CardTitle>
                        <Badge variant="outline">{channel.type}</Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-muted-foreground mb-3">{channel.description}</p>
                      <p className="text-sm text-muted-foreground mb-4">{channel.members}</p>
                      <Button 
                        className="w-full" 
                        asChild
                      >
                        <a 
                          href={
                            channel.name === "Discord Community" ? "https://discord.gg/bgSUrT2wdb" :
                            channel.name === "GitHub Discussions" ? "https://github.com/orgs/nexgen-tech-labs/discussions" : 
                            "#"
                          }
                          target="_blank" 
                          rel="noopener noreferrer"
                        >
                          Join Now
                        </a>
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <h2 className="text-2xl font-bold">Upcoming Events</h2>
              <div className="space-y-4">
                {upcomingEvents.map((event, index) => (
                  <Card key={index}>
                    <CardContent className="p-6">
                      <div className="flex justify-between items-start">
                        <div className="space-y-1">
                          <h3 className="text-lg font-semibold">{event.title}</h3>
                          <p className="text-muted-foreground">{event.date} at {event.time}</p>
                        </div>
                        <div className="text-right space-y-2">
                          <Badge variant="secondary">{event.type}</Badge>
                          <div>
                            <Button size="sm">Register</Button>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Contribute to InfraJet</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground mb-4">
                  Help us build the future of infrastructure automation. Whether you're a developer, 
                  designer, or just passionate about DevOps, there are many ways to contribute.
                </p>
                <div className="flex gap-2 flex-wrap">
                  <Button>View Open Issues</Button>
                  <Button variant="outline">Contributing Guide</Button>
                  <Button variant="outline">Code of Conduct</Button>
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

export default Community;