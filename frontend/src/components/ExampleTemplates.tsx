import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Database, Server, Shield, Globe } from "lucide-react";
interface ExampleTemplatesProps {
  onSelectExample: (example: string) => void;
  selectedProvider: string;
}
const examples = {
  aws: [{
    title: "S3 Bucket with Versioning",
    description: "Create a secure S3 bucket with versioning and encryption",
    icon: Database,
    prompt: "Create an S3 bucket with versioning enabled, server-side encryption, and public access blocked"
  }, {
    title: "EC2 Instance with Security Group",
    description: "Launch an EC2 instance with custom security group rules",
    icon: Server,
    prompt: "Create an EC2 instance with a security group allowing SSH and HTTP access"
  }, {
    title: "VPC with Subnets",
    description: "Set up a VPC with public and private subnets",
    icon: Globe,
    prompt: "Create a VPC with public and private subnets, internet gateway, and NAT gateway"
  }, {
    title: "IAM Role and Policy",
    description: "Create IAM roles with specific permissions",
    icon: Shield,
    prompt: "Create an IAM role for Lambda with S3 read/write permissions"
  }],
  azure: [{
    title: "Resource Group and Storage",
    description: "Create a resource group with storage account",
    icon: Database,
    prompt: "Create an Azure resource group with a storage account and container"
  }, {
    title: "Virtual Machine",
    description: "Deploy a virtual machine with network security group",
    icon: Server,
    prompt: "Create an Azure virtual machine with network security group and public IP"
  }, {
    title: "Virtual Network",
    description: "Set up a virtual network with subnets",
    icon: Globe,
    prompt: "Create an Azure virtual network with multiple subnets and network security groups"
  }, {
    title: "Key Vault",
    description: "Create a key vault for secrets management",
    icon: Shield,
    prompt: "Create an Azure Key Vault with access policies and secrets"
  }],
  gcp: [{
    title: "Cloud Storage Bucket",
    description: "Create a GCS bucket with lifecycle policies",
    icon: Database,
    prompt: "Create a Google Cloud Storage bucket with lifecycle management and versioning"
  }, {
    title: "Compute Engine Instance",
    description: "Launch a VM instance with firewall rules",
    icon: Server,
    prompt: "Create a Google Compute Engine instance with custom firewall rules"
  }, {
    title: "VPC Network",
    description: "Set up a VPC with custom subnets",
    icon: Globe,
    prompt: "Create a GCP VPC network with custom subnets and firewall rules"
  }, {
    title: "IAM Service Account",
    description: "Create service accounts with roles",
    icon: Shield,
    prompt: "Create a GCP service account with specific IAM roles and permissions"
  }],
  terraform: [{
    title: "Multi-Cloud Setup",
    description: "Deploy resources across multiple cloud providers",
    icon: Globe,
    prompt: "Create a Terraform configuration for multi-cloud deployment with AWS and Azure"
  }, {
    title: "Kubernetes Cluster",
    description: "Deploy a managed Kubernetes cluster",
    icon: Server,
    prompt: "Create a Terraform configuration for an EKS cluster with node groups"
  }, {
    title: "Data Pipeline",
    description: "Set up a data processing pipeline",
    icon: Database,
    prompt: "Create a Terraform configuration for a data pipeline with S3, Lambda, and RDS"
  }, {
    title: "Security Setup",
    description: "Implement security best practices",
    icon: Shield,
    prompt: "Create a Terraform configuration with security best practices including WAF and SSL"
  }]
};
const ExampleTemplates = ({
  onSelectExample,
  selectedProvider
}: ExampleTemplatesProps) => {
  const providerExamples = examples[selectedProvider as keyof typeof examples] || examples.aws;

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-foreground">Quick Start Templates</h3>
        <p className="text-xs text-muted-foreground">
          Popular configurations to get you started instantly
        </p>
      </div>
      
      <div className="space-y-2">
        {providerExamples.slice(0, 4).map((example, index) => {
          const Icon = example.icon;
          return (
            <Card key={index} className="border-card-border hover:bg-card-hover hover:shadow-sm transition-all duration-normal cursor-pointer group">
              <CardContent className="p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 flex-1">
                    <Icon className="w-4 h-4 mt-0.5 text-primary" />
                    <div className="space-y-1 flex-1">
                      <h4 className="font-medium text-xs text-foreground group-hover:text-primary transition-colors">
                        {example.title}
                      </h4>
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {example.description}
                      </p>
                    </div>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => onSelectExample(example.prompt)}
                    className="shrink-0 h-6 px-2 text-xs"
                  >
                    Try
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
      
      {providerExamples.length > 4 && (
        <p className="text-xs text-muted-foreground text-center">
          +{providerExamples.length - 4} more templates available
        </p>
      )}
    </div>
  );
};
export default ExampleTemplates;