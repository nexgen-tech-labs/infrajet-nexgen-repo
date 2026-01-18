import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Zap, Shield, Rocket, ArrowRight, Loader2 } from "lucide-react";
import { useCreateProject } from "@/hooks/useProjects";
import { useToast } from "@/hooks/use-toast";

interface WelcomeScreenProps {
  onGetStarted: () => void;
  selectedProvider: string;
  onProviderChange: (provider: string) => void;
}

const providers = [
  { id: "aws", name: "AWS", icon: "☁️", color: "from-orange-500 to-yellow-500" },
  { id: "azure", name: "Azure", icon: "🔵", color: "from-blue-500 to-cyan-500" },
  { id: "gcp", name: "Google Cloud", icon: "🟡", color: "from-green-500 to-blue-500" },
  { id: "terraform", name: "Multi-Cloud", icon: "🏗️", color: "from-purple-500 to-pink-500" },
];

const features = [
  {
    icon: <Zap className="w-6 h-6" />,
    title: "Instant Generation",
    description: "Get production-ready infrastructure code in seconds"
  },
  {
    icon: <Shield className="w-6 h-6" />,
    title: "Best Practices",
    description: "Follow security and compliance standards automatically"
  },
  {
    icon: <Rocket className="w-6 h-6" />,
    title: "Deploy Ready",
    description: "Code is ready to deploy to your cloud environment"
  }
];

const WelcomeScreen = ({ onGetStarted, selectedProvider, onProviderChange }: WelcomeScreenProps) => {
    const navigate = useNavigate();
    const { toast } = useToast();
    const [isCreating, setIsCreating] = useState(false);
    const createProjectMutation = useCreateProject();

    const generateRandomName = () => {
        const adjectives = ['Awesome', 'Amazing', 'Brilliant', 'Creative', 'Dynamic', 'Elegant', 'Fantastic', 'Great', 'Innovative', 'Magnificent'];
        const nouns = ['Project', 'Infrastructure', 'System', 'Platform', 'Solution', 'Application', 'Service', 'Network', 'Cloud', 'Deployment'];
        const randomAdjective = adjectives[Math.floor(Math.random() * adjectives.length)];
        const randomNoun = nouns[Math.floor(Math.random() * nouns.length)];
        const randomNumber = Math.floor(Math.random() * 1000);
        return `${randomAdjective} ${randomNoun} ${randomNumber}`;
    };

    const handleStartBuilding = async () => {
        setIsCreating(true);
        try {
            const projectName = generateRandomName();
            const result = await createProjectMutation.mutateAsync({
                name: projectName,
                description: `Infrastructure project created with ${selectedProvider.toUpperCase()} provider`,
            });

            // Navigate to the project dashboard
            navigate(`/projects/${result.project.id}`);
        } catch (error) {
            console.error('Failed to create project:', error);
            toast({
                title: "Failed to create project",
                description: "Please try again or contact support.",
                variant: "destructive",
            });
        } finally {
            setIsCreating(false);
        }
    };
  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-4xl mx-auto space-y-8 text-center">
        {/* Hero Section - Following Aesthetic-Usability Effect */}
        <div className="space-y-6">
          <div className="flex justify-center">
            <div className="p-4 bg-primary/10 rounded-2xl">
              <div className="text-4xl">🏗️</div>
            </div>
          </div>
          
          <div className="space-y-4">
            <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              Infrastructure as Code,
              <br />
              Generated Instantly
            </h1>
            <p className="text-lg text-foreground-secondary max-w-2xl mx-auto">
              Describe what you need, and we'll generate production-ready infrastructure code 
              following best practices and security standards.
            </p>
          </div>
        </div>

        {/* Features - Law of Proximity */}
        <div className="grid md:grid-cols-3 gap-6 my-12">
          {features.map((feature) => (
            <Card key={feature.title} className="border-card-border hover:shadow-md transition-all duration-normal">
              <CardHeader className="text-center">
                <div className="flex justify-center text-primary mb-3">
                  {feature.icon}
                </div>
                <CardTitle className="text-lg">{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-sm">
                  {feature.description}
                </CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Provider Selection - Hick's Law (reduced choices) */}
        <div className="space-y-6">
          <div className="space-y-3">
            <h2 className="text-xl font-semibold text-foreground">
              Choose Your Cloud Platform
            </h2>
            <p className="text-sm text-foreground-secondary">
              Select your preferred platform to get started
            </p>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 max-w-2xl mx-auto">
            {providers.map((provider) => (
              <Button
                key={provider.id}
                variant={selectedProvider === provider.id ? "default" : "outline"}
                size="lg"
                onClick={() => onProviderChange(provider.id)}
                className="h-20 flex flex-col items-center justify-center gap-1 p-2"
              >
                <div className={`text-2xl leading-none ${provider.id === 'aws' ? 'text-orange-500' : ''}`}>{provider.icon}</div>
                <span className="text-xs sm:text-sm font-medium text-center leading-tight">{provider.name}</span>
              </Button>
            ))}
          </div>
        </div>

        {/* CTA - Fitts' Law compliance */}
        <div className="pt-8">
          <Button
            onClick={handleStartBuilding}
            disabled={isCreating}
            size="lg"
            className="text-base px-8 py-4 h-auto"
          >
            {isCreating ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                Creating Project...
              </>
            ) : (
              <>
                Start Building
                <ArrowRight className="w-5 h-5 ml-2" />
              </>
            )}
          </Button>
          <p className="text-xs text-muted-foreground mt-3">
            Free Tier Available • Generate Your Infrastructure Code Now
          </p>
        </div>
      </div>
    </div>
  );
};

export default WelcomeScreen;