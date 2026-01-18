import { useState } from "react";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import WelcomeScreen from "@/components/WelcomeScreen";
import ProviderSelector from "@/components/ProviderSelector";
import ChatMessage from "@/components/ChatMessage";
import ChatInput from "@/components/ChatInput";
import ExampleTemplates from "@/components/ExampleTemplates";
import FileExplorer from "@/components/FileExplorer";
import CodeEditor from "@/components/CodeEditor";
import ResizablePanels from "@/components/ResizablePanels";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ChatProvider, useChat } from "@/contexts/ChatContext";
import { generateIaCCode } from "@/services/iacService";
import { useToast } from "@/hooks/use-toast";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ChevronDown, ChevronUp, ChevronLeft, ChevronRight, BookOpen, Code, Sparkles, Copy, FileText, FolderTree, Search } from "lucide-react";
import GitHubIntegration from "@/components/GitHubIntegration";
import PushToGitHubButton from "@/components/PushToGitHubButton";
import { GitHubProvider } from "@/contexts/GitHubContext";
interface Message {
  id: string;
  content: string;
  isUser: boolean;
  isCode?: boolean;
  language?: string;
}

interface FileNode {
  name: string;
  type: 'file' | 'folder';
  path: string;
  children?: FileNode[];
  content?: string;
}
const ChatContainer = () => {
  const [selectedProvider, setSelectedProvider] = useState("aws");
  const [isExamplesOpen, setIsExamplesOpen] = useState(true);
  const [showWelcome, setShowWelcome] = useState(true);
  const [isChatCollapsed, setIsChatCollapsed] = useState(false);
  const [isFileExplorerCollapsed, setIsFileExplorerCollapsed] = useState(false);
  const [isCodeEditorCollapsed, setIsCodeEditorCollapsed] = useState(false);
  const [editorRef, setEditorRef] = useState<any>(null);
  const [isProviderSelectorCollapsed, setIsProviderSelectorCollapsed] = useState(false);
  const [selectedFile, setSelectedFile] = useState<FileNode | null>(() => {
    // Set the main.tf file as default selected
    const mainTf = {
      name: "main.tf",
      type: "file" as const,
      path: "infrastructure/main.tf",
      content: `# AWS Infrastructure Configuration
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC Configuration
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "\${var.project_name}-vpc"
    Environment = var.environment
  }
}`
    };
    return mainTf;
  });
  const [projectFiles, setProjectFiles] = useState<FileNode[]>([
    {
      name: "infrastructure",
      type: "folder",
      path: "infrastructure",
      children: [
        {
          name: "main.tf",
          type: "file",
          path: "infrastructure/main.tf",
          content: `# AWS Infrastructure Configuration
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC Configuration
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "\${var.project_name}-vpc"
    Environment = var.environment
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "\${var.project_name}-igw"
    Environment = var.environment
  }
}

# Public Subnets
resource "aws_subnet" "public" {
  count = length(var.availability_zones)

  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name        = "\${var.project_name}-public-\${count.index + 1}"
    Environment = var.environment
    Type        = "Public"
  }
}

# Route Table for Public Subnets
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name        = "\${var.project_name}-public-rt"
    Environment = var.environment
  }
}

# Associate Route Table with Public Subnets
resource "aws_route_table_association" "public" {
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}`
        },
        {
          name: "variables.tf",
          type: "file",
          path: "infrastructure/variables.tf",
          content: `# Project Configuration
variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "my-aws-project"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

# Network Configuration
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-west-2a", "us-west-2b", "us-west-2c"]
}

# Instance Configuration
variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "key_pair_name" {
  description = "AWS Key Pair name for EC2 instances"
  type        = string
  default     = ""
}`
        },
        {
          name: "outputs.tf",
          type: "file",
          path: "infrastructure/outputs.tf",
          content: `# VPC Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

# Subnet Outputs
output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "public_subnet_cidrs" {
  description = "CIDR blocks of the public subnets"
  value       = aws_subnet.public[*].cidr_block
}

# Gateway Outputs
output "internet_gateway_id" {
  description = "ID of the Internet Gateway"
  value       = aws_internet_gateway.main.id
}

# Route Table Outputs
output "public_route_table_id" {
  description = "ID of the public route table"
  value       = aws_route_table.public.id
}`
        }
      ]
    },
    {
      name: "modules",
      type: "folder",
      path: "modules",
      children: [
        {
          name: "ec2",
          type: "folder",
          path: "modules/ec2",
          children: [
            {
              name: "main.tf",
              type: "file",
              path: "modules/ec2/main.tf",
              content: `# EC2 Instance Module
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_security_group" "instance" {
  name_prefix = "\${var.name_prefix}-sg"
  vpc_id      = var.vpc_id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "\${var.name_prefix}-sg"
    Environment = var.environment
  }
}

resource "aws_instance" "main" {
  count = var.instance_count

  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  key_name              = var.key_name
  vpc_security_group_ids = [aws_security_group.instance.id]
  subnet_id             = var.subnet_ids[count.index % length(var.subnet_ids)]

  user_data = var.user_data

  tags = {
    Name        = "\${var.name_prefix}-\${count.index + 1}"
    Environment = var.environment
  }
}`
            },
            {
              name: "variables.tf",
              type: "file",
              path: "modules/ec2/variables.tf",
              content: `variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs"
  type        = list(string)
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "instance_count" {
  description = "Number of instances to create"
  type        = number
  default     = 1
}

variable "key_name" {
  description = "AWS Key Pair name"
  type        = string
  default     = ""
}

variable "user_data" {
  description = "User data script"
  type        = string
  default     = ""
}`
            }
          ]
        }
      ]
    },
    {
      name: "terraform.tfvars.example",
      type: "file",
      path: "terraform.tfvars.example",
      content: `# Project Configuration
project_name = "my-awesome-project"
environment  = "production"

# AWS Configuration
aws_region = "us-west-2"
vpc_cidr   = "10.0.0.0/16"

# Instance Configuration
instance_type   = "t3.small"
key_pair_name   = "my-key-pair"

# Availability Zones
availability_zones = [
  "us-west-2a",
  "us-west-2b",
  "us-west-2c"
]`
    },
    {
      name: "README.md",
      type: "file",
      path: "README.md",
      content: `# AWS Infrastructure with Terraform

This project contains Terraform configurations for deploying AWS infrastructure.

## Prerequisites

- [Terraform](https://www.terraform.io/downloads.html) >= 1.0
- [AWS CLI](https://aws.amazon.com/cli/) configured with appropriate credentials
- An AWS account with necessary permissions

## Quick Start

1. **Clone and Navigate**
   \`\`\`bash
   git clone <repository-url>
   cd infrastructure
   \`\`\`

2. **Configure Variables**
   \`\`\`bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your specific values
   \`\`\`

3. **Initialize Terraform**
   \`\`\`bash
   terraform init
   \`\`\`

4. **Plan Deployment**
   \`\`\`bash
   terraform plan
   \`\`\`

5. **Apply Configuration**
   \`\`\`bash
   terraform apply
   \`\`\`

## Architecture

This configuration creates:

- **VPC** with custom CIDR block
- **Public Subnets** across multiple AZs
- **Internet Gateway** for public internet access
- **Route Tables** for proper traffic routing
- **Security Groups** with basic web and SSH access

## Modules

### EC2 Module
Located in \`modules/ec2/\`, this module creates:
- EC2 instances with configurable count
- Security groups with web and SSH access
- Auto-scaling across multiple subnets

## Customization

### Variables
All configurable options are defined in \`variables.tf\`:
- \`project_name\`: Name prefix for all resources
- \`environment\`: Environment tag (dev, staging, prod)
- \`vpc_cidr\`: VPC CIDR block
- \`instance_type\`: EC2 instance size

### Outputs
Key infrastructure details are exported in \`outputs.tf\`:
- VPC ID and CIDR
- Subnet IDs and CIDRs
- Gateway and route table IDs

## Security Considerations

- Review security group rules before deployment
- Use least-privilege IAM policies
- Enable VPC Flow Logs for monitoring
- Consider using AWS Systems Manager for instance access

## Cleanup

To destroy all resources:
\`\`\`bash
terraform destroy
\`\`\`

## Support

For issues and questions, please refer to the [Terraform AWS Provider documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs).`
    }
  ]);
  const {
    messages,
    addMessage,
    isLoading,
    setIsLoading,
    abortController,
    setAbortController
  } = useChat();
  const { toast } = useToast();

  const handleGetStarted = () => {
    setShowWelcome(false);
  };
  const handleSendMessage = async (message: string) => {
    try {
      addMessage({
        content: message,
        isUser: true
      });
      setIsLoading(true);

      // Create new AbortController for this request
      const controller = new AbortController();
      setAbortController(controller);
      const conversationHistory = messages.map(msg => ({
        content: msg.content,
        isUser: msg.isUser,
        isCode: msg.isCode
      }));
      const response = await generateIaCCode({
        prompt: message,
        provider: selectedProvider,
        conversationHistory,
        signal: controller.signal
      });
      addMessage({
        content: `Here's the ${selectedProvider.toUpperCase()} infrastructure code for your request:`,
        isUser: false
      });
      addMessage({
        content: response.generatedCode,
        isUser: false,
        isCode: true,
        language: selectedProvider === 'terraform' ? 'hcl' : selectedProvider
      });

      // Create file structure from generated code
      const fileName = `main.${selectedProvider === 'terraform' ? 'tf' : 'yaml'}`;
      const newFile: FileNode = {
        name: fileName,
        type: 'file',
        path: fileName,
        content: response.generatedCode
      };

      // Update project files
      setProjectFiles(prev => {
        const existing = prev.find(f => f.path === fileName);
        if (existing) {
          return prev.map(f => f.path === fileName ? newFile : f);
        }
        return [...prev, newFile];
      });

      // Auto-select the new file
      setSelectedFile(newFile);
      if (response.usage) {
        console.log('Token usage:', response.usage);
      }
    } catch (error) {
      console.error('Error generating IaC code:', error);
      if (error.name === 'AbortError') {
        addMessage({
          content: "Generation stopped by user.",
          isUser: false
        });
        toast({
          title: "Generation Stopped",
          description: "Code generation was stopped successfully."
        });
      } else {
        addMessage({
          content: `I apologize, but I encountered an error while generating the infrastructure code: ${error.message}. Please try again or rephrase your request.`,
          isUser: false
        });
        toast({
          title: "Error",
          description: "Failed to generate infrastructure code. Please try again.",
          variant: "destructive"
        });
      }
    } finally {
      setIsLoading(false);
      setAbortController(null);
    }
  };
  const handleStopGeneration = () => {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
      setIsLoading(false);
    }
  };
  const handleSelectExample = (example: string) => {
    handleSendMessage(example);
    setIsExamplesOpen(false);
  };

  const handleCopyCode = async () => {
    if (latestCode) {
      try {
        await navigator.clipboard.writeText(latestCode.content);
        toast({
          title: "Code Copied",
          description: "The generated code has been copied to your clipboard."
        });
      } catch (error) {
        toast({
          title: "Copy Failed",
          description: "Failed to copy code to clipboard.",
          variant: "destructive"
        });
      }
    }
  };
  const codeMessages = messages.filter(msg => msg.isCode);
  const latestCode = codeMessages[codeMessages.length - 1];

  const handleFileSelect = (file: FileNode) => {
    setSelectedFile(file);
  };

  const handleCodeChange = (value: string | undefined) => {
    if (selectedFile && value !== undefined) {
      const updatedFile = { ...selectedFile, content: value };
      setSelectedFile(updatedFile);

      // Update the file in the project files
      setProjectFiles(prev =>
        prev.map(f => f.path === selectedFile.path ? updatedFile : f)
      );
    }
  };

  // Show welcome screen first (Progressive Disclosure)
  if (showWelcome) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <WelcomeScreen
          onGetStarted={handleGetStarted}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
        />
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
      <Header />

      <div className="h-[calc(100vh-64px)]">
        <ResizablePanels
          defaultSizes={isChatCollapsed ? [5, 95] : [35, 65]}
          minSizes={isChatCollapsed ? [5, 30] : [25, 30]}
          leftPanel={
            /* Left Panel - Chat Interface */
            <div className="flex flex-col h-full bg-background/95 backdrop-blur-sm border-r border-border/50">
              {/* Provider Selector */}
              <div className="border-b border-border/50 bg-gradient-to-r from-muted/30 to-muted/10">
                <ProviderSelector
                  selectedProvider={selectedProvider}
                  onProviderChange={setSelectedProvider}
                  isCollapsed={isProviderSelectorCollapsed}
                  onToggleCollapse={() => setIsProviderSelectorCollapsed(!isProviderSelectorCollapsed)}
                />
              </div>

              {/* Chat Header */}
              <div className="border-b border-border/50 p-4 bg-gradient-to-r from-muted/30 to-muted/10 flex items-center justify-between">
                <span className="font-medium text-sm">Chat</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsChatCollapsed(!isChatCollapsed)}
                  className="h-6 w-6 p-0"
                >
                  {isChatCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
                </Button>
              </div>

              {/* Chat Content */}
              {!isChatCollapsed && (
                <>
                  {/* Examples Section */}
                  <Collapsible open={isExamplesOpen} onOpenChange={setIsExamplesOpen}>
                    <CollapsibleTrigger asChild>
                      <Button
                        variant="ghost"
                        className="w-full justify-between p-4 h-auto border-b border-border/50 rounded-none hover:bg-muted/30 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <div className="p-1.5 rounded-lg bg-primary/10">
                            <BookOpen className="w-4 h-4 text-primary" />
                          </div>
                          <span className="font-medium">Templates</span>
                          <span className="text-xs bg-gradient-to-r from-primary/20 to-primary/10 text-primary px-2 py-1 rounded-full border border-primary/20">
                            Quick Start
                          </span>
                        </div>
                        {isExamplesOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </Button>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="border-b border-border/50">
                      <div className="p-4 max-h-64 overflow-y-auto bg-muted/20">
                        <ExampleTemplates onSelectExample={handleSelectExample} selectedProvider={selectedProvider} />
                      </div>
                    </CollapsibleContent>
                  </Collapsible>

                  {/* Chat Messages */}
                  <ScrollArea className="flex-1 p-6">
                    {messages.length === 0 ? (
                      <div className="flex items-center justify-center h-full text-center">
                        <div className="space-y-8 max-w-md">
                          <div className="relative">
                            <div className="p-6 bg-gradient-to-br from-primary/20 via-primary/10 to-transparent rounded-3xl w-fit mx-auto border border-primary/20 shadow-lg">
                              <Sparkles className="w-10 h-10 text-primary" />
                            </div>
                            <div className="absolute -top-1 -right-1 w-4 h-4 bg-gradient-to-r from-green-400 to-emerald-500 rounded-full animate-pulse"></div>
                          </div>
                          <div className="space-y-4">
                            <h2 className="text-2xl font-bold bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                              Ready to Build?
                            </h2>
                            <p className="text-muted-foreground leading-relaxed">
                              Describe your infrastructure needs in plain English.
                              I'll generate production-ready code following best practices.
                            </p>
                          </div>
                          <div className="flex items-center justify-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-primary/10 via-primary/5 to-transparent border border-primary/20 text-primary text-sm font-medium w-fit mx-auto">
                            <Sparkles className="w-4 h-4" />
                            AI-Powered Generation
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {messages.filter(msg => !msg.isCode).map(message => (
                          <ChatMessage
                            key={message.id}
                            message={message.content}
                            isUser={message.isUser}
                            isCode={message.isCode}
                            language={message.language}
                          />
                        ))}
                      </div>
                    )}
                  </ScrollArea>

                  {/* Chat Input */}
                  <ChatInput
                    onSendMessage={handleSendMessage}
                    onStopGeneration={handleStopGeneration}
                    isLoading={isLoading}
                  />
                </>
              )}
            </div>
          }
          rightPanel={
            /* Right Panel - File Explorer & Code Editor */
            <ResizablePanels
              defaultSizes={isFileExplorerCollapsed ? [8, 92] : [30, 70]}
              minSizes={isFileExplorerCollapsed ? [8, 40] : [20, 40]}
              collapsedRight={isCodeEditorCollapsed}
              leftPanel={
                /* File Explorer */
                <div className="h-full bg-background/95 backdrop-blur-sm">
                  <FileExplorer
                    files={projectFiles}
                    onFileSelect={handleFileSelect}
                    selectedFile={selectedFile}
                    isCollapsed={isFileExplorerCollapsed}
                    onToggleCollapse={() => setIsFileExplorerCollapsed(!isFileExplorerCollapsed)}
                  />
                </div>
              }
              rightPanel={
                /* Code Editor & Actions */
                <div className={`flex ${isCodeEditorCollapsed ? 'flex-row' : 'flex-col'} h-full bg-background/95 backdrop-blur-sm transition-all duration-300 ease-in-out`}>
                  {/* Header with actions */}
                  <div className={`flex items-center ${isCodeEditorCollapsed ? 'flex-col p-2 gap-2 border-r border-border/50' : 'justify-between p-4 border-b border-border/50'} bg-gradient-to-r from-muted/30 to-muted/10 transition-all duration-300 ease-in-out`}>
                    <div className={`flex items-center ${isCodeEditorCollapsed ? 'flex-col gap-1' : 'gap-3'}`}>
                      {selectedFile ? (
                        <>
                          <div className="p-1.5 rounded-lg bg-primary/10">
                            <FileText className="w-4 h-4 text-primary" />
                          </div>
                          <div className={`${isCodeEditorCollapsed ? 'text-center' : ''}`}>
                            <span className="text-xs font-semibold">{selectedFile.name}</span>
                            {!isCodeEditorCollapsed && (
                              <div className="flex items-center gap-2 mt-0.5">
                                <span className="text-xs text-muted-foreground">{selectedFile.path}</span>
                                <span className="text-xs bg-gradient-to-r from-green-100 to-emerald-100 dark:from-green-900/20 dark:to-emerald-900/20 text-green-700 dark:text-green-400 px-2 py-0.5 rounded-full border border-green-200 dark:border-green-800">
                                  Active
                                </span>
                              </div>
                            )}
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="p-1.5 rounded-lg bg-muted/50">
                            <Code className="w-4 h-4 text-muted-foreground" />
                          </div>
                          <span className="text-xs text-muted-foreground">No file</span>
                        </>
                      )}
                    </div>

                    <div className={`flex items-center ${isCodeEditorCollapsed ? 'flex-col gap-1' : 'gap-2'}`}>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setIsCodeEditorCollapsed(!isCodeEditorCollapsed)}
                        className="h-6 w-6 p-0"
                      >
                        {isCodeEditorCollapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                      </Button>
                      {!isCodeEditorCollapsed && selectedFile && (
                       <>
                         <Button
                           variant="outline"
                           size="sm"
                           onClick={() => editorRef?.getAction('actions.find')?.run()}
                           className="gap-2"
                         >
                           <Search className="w-3 h-3" />
                           Find
                         </Button>
                         <Button
                           variant="outline"
                           size="sm"
                           onClick={() => {
                             if (selectedFile.content) {
                               navigator.clipboard.writeText(selectedFile.content);
                               toast({
                                 title: "Code Copied",
                                 description: "File content copied to clipboard."
                               });
                             }
                           }}
                           className="gap-2"
                         >
                           <Copy className="w-3 h-3" />
                           Copy
                         </Button>
                          <PushToGitHubButton
                            code={selectedFile.content || ''}
                            provider={selectedProvider}
                            filename={selectedFile.name}
                          />
                        </>
                      )}
                      {!isCodeEditorCollapsed && <GitHubIntegration />}
                    </div>
                  </div>

                  {/* Code Editor */}
                  {!isCodeEditorCollapsed && (
                    <div className="flex-1 overflow-hidden">
                      {selectedFile ? (
                        <CodeEditor
                          value={selectedFile.content || ''}
                          language={selectedFile.name.split('.').pop() || 'plaintext'}
                          onChange={handleCodeChange}
                          onEditorMount={setEditorRef}
                          height="100%"
                        />
                      ) : (
                        <div className="flex items-center justify-center h-full text-center">
                          <div className="space-y-4 max-w-sm">
                            <div className="p-3 bg-muted/50 rounded-xl w-fit mx-auto">
                              <FolderTree className="w-8 h-8 text-muted-foreground" />
                            </div>
                            <div className="space-y-2">
                              <h3 className="font-medium">Select a File</h3>
                              <p className="text-muted-foreground text-sm">
                                Choose a file from the explorer to view and edit its contents.
                                Generated code will appear here automatically.
                              </p>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              }
            />
          }
        />
      </div>

      <Footer />
    </div>
  );
};
const Index = () => {
  return <GitHubProvider>
    <ChatProvider>
      <ChatContainer />
    </ChatProvider>
  </GitHubProvider>;
};
export default Index;