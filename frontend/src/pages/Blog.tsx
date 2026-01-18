import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const Blog = () => {
  const blogPosts = [
    {
      title: "The Future of Infrastructure as Code",
      excerpt: "Exploring how AI is revolutionizing the way we manage cloud infrastructure and deployment automation.",
      author: "John Smith",
      date: "December 15, 2024",
      category: "Technology",
      readTime: "5 min read"
    },
    {
      title: "Best Practices for Multi-Cloud Deployments",
      excerpt: "Learn essential strategies for managing infrastructure across multiple cloud providers effectively.",
      author: "Sarah Johnson",
      date: "December 10, 2024",
      category: "Best Practices",
      readTime: "8 min read"
    },
    {
      title: "Security First: Protecting Your Infrastructure",
      excerpt: "A comprehensive guide to implementing security best practices in your infrastructure as code workflows.",
      author: "Mike Chen",
      date: "December 5, 2024",
      category: "Security",
      readTime: "12 min read"
    }
  ];

  const categories = ["All", "Technology", "Best Practices", "Security", "Tutorials", "Case Studies"];

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 bg-gradient-to-br from-background to-muted/20">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-6xl mx-auto space-y-8">
            <div className="text-center space-y-4">
              <h1 className="text-4xl font-bold tracking-tight">Blog</h1>
              <p className="text-xl text-muted-foreground">
                Insights, tutorials, and updates from the infraJet team
              </p>
            </div>

            <div className="flex flex-wrap gap-2 justify-center">
              {categories.map((category) => (
                <Badge 
                  key={category}
                  variant={category === "All" ? "default" : "secondary"}
                  className="cursor-pointer"
                >
                  {category}
                </Badge>
              ))}
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {blogPosts.map((post, index) => (
                <Card key={index} className="cursor-pointer hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <div className="flex justify-between items-start mb-2">
                      <Badge variant="outline">{post.category}</Badge>
                      <span className="text-sm text-muted-foreground">{post.readTime}</span>
                    </div>
                    <CardTitle className="line-clamp-2">{post.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-muted-foreground mb-4 line-clamp-3">
                      {post.excerpt}
                    </p>
                    <div className="flex justify-between items-center text-sm text-muted-foreground">
                      <span>By {post.author}</span>
                      <span>{post.date}</span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            <div className="text-center">
              <Button>Load More Posts</Button>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Subscribe to Our Newsletter</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground mb-4">
                  Get the latest blog posts, product updates, and industry insights delivered to your inbox.
                </p>
                <div className="flex gap-2 max-w-md mx-auto">
                  <input 
                    type="email" 
                    placeholder="Enter your email"
                    className="flex-1 px-3 py-2 border border-input rounded-md"
                  />
                  <Button>Subscribe</Button>
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

export default Blog;