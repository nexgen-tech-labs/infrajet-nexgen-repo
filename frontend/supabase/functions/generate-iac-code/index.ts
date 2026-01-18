
import "https://deno.land/x/xhr@0.1.0/mod.ts";
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const openAIApiKey = Deno.env.get('OPENAI_API_KEY');

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const providerPrompts = {
  aws: {
    systemPrompt: `You are an expert AWS infrastructure architect and Terraform specialist. Generate production-ready Terraform code for AWS resources with:
- Best practices for security, scalability, and cost optimization
- Proper resource naming conventions and tagging
- Security groups, IAM roles, and encryption configurations
- VPC, subnet, and networking best practices
- Comments explaining key decisions and configurations
- Variables and outputs where appropriate

Always include security considerations and follow AWS Well-Architected Framework principles.`,
    examples: {
      s3: "Create an S3 bucket with versioning, encryption, and public access blocked",
      ec2: "Create an EC2 instance with security groups for web server",
      vpc: "Create a VPC with public and private subnets",
      rds: "Create an RDS PostgreSQL database with encryption and backup"
    }
  },
  azure: {
    systemPrompt: `You are an expert Azure infrastructure architect and Terraform specialist. Generate production-ready Terraform code for Azure resources with:
- Azure Resource Manager (ARM) best practices
- Resource groups and proper naming conventions
- Network security groups and virtual networks
- Azure Key Vault for secrets management
- Managed identity configurations
- Cost optimization and resource tagging
- Comments explaining Azure-specific considerations

Follow Azure Well-Architected Framework principles and security best practices.`,
    examples: {
      vm: "Create a virtual machine with network security group",
      storage: "Create a storage account with encryption and access controls",
      vnet: "Create a virtual network with subnets and NSGs",
      database: "Create an Azure SQL database with encryption"
    }
  },
  gcp: {
    systemPrompt: `You are an expert Google Cloud Platform architect and Terraform specialist. Generate production-ready Terraform code for GCP resources with:
- Google Cloud best practices and naming conventions
- IAM roles and service accounts configuration
- VPC networks and firewall rules
- Cloud Storage bucket policies
- Compute Engine security and networking
- Resource organization and labeling
- Comments explaining GCP-specific features

Follow Google Cloud Architecture Framework and security best practices.`,
    examples: {
      compute: "Create a Compute Engine instance with firewall rules",
      storage: "Create a Cloud Storage bucket with IAM policies",
      network: "Create a VPC network with subnets and firewall rules",
      database: "Create a Cloud SQL PostgreSQL instance"
    }
  },
  terraform: {
    systemPrompt: `You are an expert Terraform architect specializing in multi-cloud infrastructure. Generate production-ready Terraform code with:
- Provider-agnostic best practices
- Modular code structure with variables and outputs
- State management considerations
- Resource dependencies and lifecycle management
- Conditional logic and dynamic blocks
- Comprehensive commenting and documentation
- Error handling and validation

Focus on creating reusable, maintainable infrastructure code.`,
    examples: {
      module: "Create a reusable Terraform module for common infrastructure",
      state: "Set up remote state management with backend configuration",
      variables: "Create comprehensive variable definitions with validation",
      outputs: "Define useful outputs for infrastructure components"
    }
  }
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { prompt, provider = 'aws', conversationHistory = [] } = await req.json();

    if (!openAIApiKey) {
      throw new Error('OpenAI API key not configured');
    }

    const selectedProvider = providerPrompts[provider as keyof typeof providerPrompts] || providerPrompts.aws;
    
    // Build conversation context
    const messages = [
      { role: 'system', content: selectedProvider.systemPrompt },
      ...conversationHistory.map((msg: any) => ({
        role: msg.isUser ? 'user' : 'assistant',
        content: msg.content
      })).slice(-10), // Keep last 10 messages for context
      { role: 'user', content: prompt }
    ];

    console.log('Generating IaC code for provider:', provider);
    console.log('User prompt:', prompt);

    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${openAIApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages,
        max_tokens: 2000,
        temperature: 0.3,
        stream: false
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(`OpenAI API error: ${response.status} - ${errorData.error?.message || 'Unknown error'}`);
    }

    const data = await response.json();
    const generatedCode = data.choices[0].message.content;

    console.log('Successfully generated IaC code');

    return new Response(JSON.stringify({ 
      generatedCode,
      provider,
      usage: data.usage
    }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });

  } catch (error) {
    console.error('Error in generate-iac-code function:', error);
    return new Response(JSON.stringify({ 
      error: error.message || 'Failed to generate infrastructure code'
    }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
