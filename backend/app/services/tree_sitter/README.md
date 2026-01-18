# Tree-Sitter Service for Terraform

A FastAPI service for parsing and analyzing Terraform configuration files using tree-sitter-like parsing techniques.

## Features

- **Terraform Parsing**: Parse `.tf` files to extract resources, modules, variables, and outputs
- **Directory Analysis**: Analyze entire Terraform projects recursively
- **Resource Search**: Find specific resource types across multiple files
- **Syntax Validation**: Basic Terraform syntax validation
- **Project Insights**: Generate statistics and recommendations for Terraform projects
- **Multi-format Support**: Support for `.tf`, `.tfvars`, `.hcl`, `.yaml`, `.json` files

## Installation

The service is part of your FastAPI application. Install the required dependencies:

```bash
# Install with uv (recommended - includes python-hcl2)
uv sync

# Or install manually with pip
pip install python-hcl2 pyyaml tree-sitter

# Optional: Enhanced tree-sitter support (requires manual setup)
# Note: tree-sitter language bindings need to be built from source
# See: https://github.com/tree-sitter/py-tree-sitter#installation
```

### Tree-sitter Language Bindings (Advanced)

For the most accurate parsing, you can manually install tree-sitter language bindings:

```bash
# Install tree-sitter CLI
npm install -g tree-sitter-cli

# Clone and build HCL grammar
git clone https://github.com/MichaHoffmann/tree-sitter-hcl
cd tree-sitter-hcl
tree-sitter generate
# Follow py-tree-sitter documentation to build Python bindings
```

### Parser Strategy

The service uses a multi-tier parsing strategy for maximum compatibility and accuracy:

1. **python-hcl2 (Recommended)**: Robust HCL parsing, handles most Terraform syntax correctly
2. **Tree-sitter (Advanced)**: Most accurate, requires manual setup of language bindings
3. **Regex fallback**: Basic parsing, always available but limited

The parser automatically selects the best available option and falls back gracefully if needed.

## Usage

### 1. Basic Service Usage

```python
from app.services.tree_sitter_service import TreeSitterService

# Initialize the service
service = TreeSitterService()

# Parse a single Terraform file
result = await service.parse_terraform_file("path/to/main.tf")

# Parse an entire directory
directory_result = await service.parse_terraform_directory("path/to/terraform/project")

# Get specific components
resources = await service.get_terraform_resources("path/to/main.tf")
modules = await service.get_terraform_modules("path/to/main.tf")
variables = await service.get_terraform_variables("path/to/variables.tf")
outputs = await service.get_terraform_outputs("path/to/outputs.tf")
```

### 2. API Endpoints

The service provides REST API endpoints for all functionality:

#### Parse Single File
```http
POST /terraform/parse/file
Content-Type: application/json

{
  "file_path": "path/to/main.tf"
}
```

#### Parse Directory
```http
POST /terraform/parse/directory
Content-Type: application/json

{
  "directory_path": "path/to/terraform/project",
  "recursive": true,
  "max_files": 100
}
```

#### Get Resources
```http
POST /terraform/resources
Content-Type: application/json

{
  "file_path": "path/to/main.tf"
}
```

#### Search Resources by Type
```http
POST /terraform/search/resources
Content-Type: application/json

{
  "directory_path": "path/to/terraform/project",
  "resource_type": "aws_instance"
}
```

#### Analyze Project
```http
POST /terraform/analyze
Content-Type: application/json

{
  "directory_path": "path/to/terraform/project"
}
```

### 3. Example Responses

#### Resource Extraction
```json
[
  {
    "type": "aws_vpc",
    "name": "main",
    "line_start": 15,
    "line_end": 25,
    "content": "resource \"aws_vpc\" \"main\" {\n  cidr_block = \"10.0.0.0/16\"\n  ...\n}",
    "attributes": {
      "cidr_block": "10.0.0.0/16",
      "enable_dns_hostnames": "true"
    }
  }
]
```

#### Project Analysis
```json
{
  "project_path": "path/to/terraform/project",
  "summary": {
    "total_files": 5,
    "successful_parses": 5,
    "failed_parses": 0,
    "total_resources": 12,
    "total_modules": 3,
    "total_variables": 8,
    "total_outputs": 4
  },
  "resource_types": {
    "aws_vpc": 1,
    "aws_subnet": 4,
    "aws_instance": 2,
    "aws_security_group": 2
  },
  "errors": [],
  "files": [...]
}
```

## Supported File Types

- `.tf` - Terraform configuration files
- `.tfvars` - Terraform variable files
- `.hcl` - HashiCorp Configuration Language files
- `.yaml`, `.yml` - YAML files
- `.json` - JSON files

## Architecture

The service consists of several components:

1. **TerraformParser** (`terraform_parser.py`): Multi-strategy parsing with tree-sitter, HCL2, and regex fallback
2. **HCLParser** (`hcl_parser.py`): Dedicated python-hcl2 parser for robust HCL parsing
3. **TreeSitterService** (`tree_sitter_service.py`): Base service with file handling and coordination
4. **TreeSitterService** (`../tree_sitter_service.py`): FastAPI wrapper with HTTP exception handling
5. **API Routes** (`../../api/routes/terraform.py`): REST API endpoints

### Parser Selection Logic

```python
# Priority order:
1. python-hcl2 (robust HCL parsing) - Available via uv/pip
2. Tree-sitter (most accurate) - Requires manual language binding setup
3. Regex fallback (basic but always available)
```

## Testing

Run the test file to verify functionality:

```bash
cd app/services/tree-sitter
python test_terraform_parser.py
```

## Error Handling

The service provides comprehensive error handling:

- **File not found**: Returns appropriate HTTP 400 errors
- **Parsing errors**: Captured and returned in response
- **Invalid syntax**: Reported through validation endpoints
- **Service errors**: Logged and returned as HTTP 500 errors

## Performance Considerations

- **File limits**: Directory parsing is limited to 100 files by default
- **Async processing**: All operations are asynchronous for better performance
- **Memory efficient**: Processes files individually to avoid memory issues
- **Concurrent parsing**: Multiple files parsed concurrently when analyzing directories

## Extending the Service

To add support for new file types:

1. Add the extension to `SUPPORTED_EXTENSIONS` in `tree_sitter_service.py`
2. Implement a parser method in `_parse_content_by_type()`
3. Add corresponding query patterns if needed

To add new Terraform constructs:

1. Extend the parsing methods in `terraform_parser.py`
2. Add new data classes for the constructs
3. Update the API endpoints to expose the new functionality

## Common Use Cases

1. **Infrastructure Auditing**: Analyze Terraform projects for compliance and best practices
2. **Resource Discovery**: Find all resources of specific types across large codebases
3. **Dependency Analysis**: Understand module dependencies and relationships
4. **Code Quality**: Validate Terraform syntax and structure
5. **Migration Planning**: Analyze existing infrastructure before migrations
6. **Documentation**: Generate documentation from Terraform code structure