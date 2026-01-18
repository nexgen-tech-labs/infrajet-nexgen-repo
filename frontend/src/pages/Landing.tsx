import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

const Landing = () => {
  return (
    <div className="min-h-screen bg-white">
      <Header />
      
      {/* Hero Section */}
      <main className="flex-1">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="text-center space-y-8">
            {/* Logo Icon */}
            <div className="text-8xl mb-8">🏗️</div>
            
            {/* Main Heading */}
            <div className="space-y-4">
              <h1 className="text-5xl md:text-6xl font-bold text-slate-900">
                Welcome to infraJet
              </h1>
              <p className="text-xl md:text-2xl text-slate-600 max-w-4xl mx-auto leading-relaxed">
                Your AI-powered Infrastructure as Code assistant. Generate 
                production-ready Terraform, AWS CloudFormation, Azure ARM templates, 
                and Google Cloud configurations.
              </p>
            </div>
            
            {/* Performance Claims */}
            <div className="space-y-2">
              <p className="text-2xl md:text-3xl font-bold text-slate-800">
                Supercharge Your DevOps Team by 40x
              </p>
              <p className="text-xl md:text-2xl font-semibold text-slate-700">
                Deploy infrastructure 50x Times faster
              </p>
            </div>
            
            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-8">
              <Button 
                asChild 
                size="lg" 
                className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 text-lg font-semibold"
              >
                <Link to="/auth">Get Started</Link>
              </Button>
              <Button 
                asChild 
                variant="outline" 
                size="lg"
                className="border-slate-400 text-slate-600 hover:bg-slate-100 px-8 py-4 text-lg"
              >
                <Link to="/docs">Learn More</Link>
              </Button>
            </div>
            
            {/* Feature Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-blue-600/20 to-purple-600/20 text-blue-600 text-sm font-medium shadow-lg">
              ✨ Powered by Claude
            </div>
          </div>
        </div>
      </main>
      
      <Footer />
    </div>
  );
};

export default Landing;