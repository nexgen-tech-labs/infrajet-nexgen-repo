"""
Terraform-specific parser using multiple parsing strategies.

This module provides robust Terraform configuration parsing using multiple
strategies in order of preference:
1. python-hcl2 (most reliable)
2. tree-sitter (fastest, requires language bindings)
3. regex fallback (always available)
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import json
import asyncio
from pathlib import Path

try:
    import tree_sitter
    from tree_sitter import Language, Parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from .hcl_parser import HCLParser
from logconfig.logger import get_logger

logger = get_logger()


@dataclass
class TerraformResource:
    """
    Represents a Terraform resource definition.

    Attributes:
        type: Resource type (e.g., 'aws_instance')
        name: Resource name identifier
        line_start: Starting line number in source file
        line_end: Ending line number in source file
        content: Raw content of the resource block
        attributes: Parsed attributes and their values
    """

    type: str
    name: str
    line_start: int
    line_end: int
    content: str
    attributes: Dict[str, Any]


@dataclass
class TerraformModule:
    """
    Represents a Terraform module definition.

    Attributes:
        name: Module name identifier
        source: Module source path or URL
        line_start: Starting line number in source file
        line_end: Ending line number in source file
        content: Raw content of the module block
        variables: Module input variables
    """

    name: str
    source: str
    line_start: int
    line_end: int
    content: str
    variables: Dict[str, Any]


@dataclass
class TerraformVariable:
    """
    Represents a Terraform variable definition.

    Attributes:
        name: Variable name
        type: Variable type constraint
        default: Default value if any
        description: Variable description
        line_start: Starting line number in source file
        line_end: Ending line number in source file
    """

    name: str
    type: Optional[str]
    default: Optional[Any]
    description: Optional[str]
    line_start: int
    line_end: int


@dataclass
class TerraformOutput:
    """
    Represents a Terraform output definition.

    Attributes:
        name: Output name
        value: Output value expression
        description: Output description
        sensitive: Whether output is marked as sensitive
        line_start: Starting line number in source file
        line_end: Ending line number in source file
    """

    name: str
    value: str
    description: Optional[str]
    sensitive: bool
    line_start: int
    line_end: int


class TerraformParser:
    """
    Parser for Terraform configuration files using multiple parsing strategies.

    This parser automatically selects the best available parsing strategy:
    1. python-hcl2: Most reliable, handles complex HCL syntax
    2. tree-sitter: Fastest, requires language bindings installation
    3. regex fallback: Always available, handles basic cases
    """

    def __init__(self):
        """Initialize the Terraform parser with available strategies."""
        self.resources: List[TerraformResource] = []
        self.modules: List[TerraformModule] = []
        self.variables: List[TerraformVariable] = []
        self.outputs: List[TerraformOutput] = []
        self.providers: List[Dict[str, Any]] = []

        # Initialize parsers
        self.tree_sitter_parser = None
        self.language = None
        self.hcl_parser = HCLParser()

        # Determine best available parser
        self.parser_strategy = self._determine_parser_strategy()
        logger.info(
            f"Terraform parser initialized with strategy: {self.parser_strategy}"
        )

        if self.parser_strategy == "tree_sitter":
            self._initialize_tree_sitter()

    def _determine_parser_strategy(self) -> str:
        """Determine the best available parsing strategy."""
        # Priority: python-hcl2 > tree-sitter > regex fallback
        # Note: tree-sitter language bindings need manual installation

        if self.hcl_parser.is_available():
            return "hcl2"

        if TREE_SITTER_AVAILABLE:
            try:
                # Try to import HCL language bindings (manually installed)
                import tree_sitter_hcl

                return "tree_sitter"
            except ImportError:
                try:
                    import tree_sitter_terraform

                    return "tree_sitter"
                except ImportError:
                    pass

        return "regex"

    def _initialize_tree_sitter(self):
        """Initialize tree-sitter parser with HCL language."""
        if not TREE_SITTER_AVAILABLE:
            return

        try:
            # Try to load HCL language
            import tree_sitter_hcl as tshcl

            self.language = Language(tshcl.language(), "hcl")
            self.tree_sitter_parser = Parser()
            self.tree_sitter_parser.set_language(self.language)
            logger.info("Using tree-sitter HCL parser")

        except ImportError:
            try:
                # Alternative: use tree-sitter-terraform if available
                import tree_sitter_terraform as tsterraform

                self.language = Language(tsterraform.language(), "terraform")
                self.tree_sitter_parser = Parser()
                self.tree_sitter_parser.set_language(self.language)
                logger.info("Using tree-sitter Terraform parser")
            except ImportError:
                logger.warning("tree-sitter HCL/Terraform not available")
                self.parser_strategy = (
                    "hcl2" if self.hcl_parser.is_available() else "regex"
                )

    def parse_content(
        self, content: str, file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Parse Terraform content using the best available parser with production features."""
        self._reset()

        try:
            if self.parser_strategy == "tree_sitter" and self.tree_sitter_parser:
                return self._parse_with_tree_sitter(content, file_path)
            elif self.parser_strategy == "hcl2":
                return self._parse_with_hcl2(content, file_path)
            else:
                return self._parse_with_regex_fallback(content)
        except (ValueError, MemoryError, TimeoutError) as e:
            # Production-level errors should not fallback
            logger.error(f"Production parser failed ({self.parser_strategy}): {e}")
            raise
        except Exception as e:
            logger.warning(f"Primary parser failed ({self.parser_strategy}): {e}")
            # Fallback to regex if primary parser fails
            if self.parser_strategy != "regex":
                return self._parse_with_regex_fallback(content)
            raise

    async def parse_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Parse a Terraform file by reading its content and using tree-sitter parsing.

        Args:
            file_path: Path to the Terraform file (str or Path object)

        Returns:
            Dict containing parsed Terraform data with resources, modules, variables, etc.

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the path is not a file
            Exception: For parsing errors
        """
        try:
            path = Path(file_path)

            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            if not path.is_file():
                raise ValueError(f"Path is not a file: {file_path}")

            # Read file content asynchronously
            content = await asyncio.to_thread(lambda: path.read_text(encoding='utf-8'))

            # Use tree-sitter parsing method
            return self._parse_with_tree_sitter(content, str(file_path))

        except (FileNotFoundError, ValueError):
            raise
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            raise

    def _parse_with_hcl2(
        self, content: str, file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Parse using production-ready python-hcl2 library."""
        try:
            # Use production HCL parser with line numbers and caching
            parsed_data = self.hcl_parser.parse_content(content, file_path)

            # Convert HCL2 format to our internal format
            self._convert_hcl2_to_internal_format(parsed_data)

            result = {
                "resources": [self._resource_to_dict(r) for r in self.resources],
                "modules": [self._module_to_dict(m) for m in self.modules],
                "variables": [self._variable_to_dict(v) for v in self.variables],
                "outputs": [self._output_to_dict(o) for o in self.outputs],
                "providers": self.providers,
                "data_sources": parsed_data.get("data", []),
                "locals": parsed_data.get("locals", []),
                "terraform_blocks": parsed_data.get("terraform", []),
            }

            # Add metadata from HCL parser
            if "_metadata" in parsed_data:
                result["_metadata"] = parsed_data["_metadata"]

            return result

        except (ValueError, MemoryError, TimeoutError) as e:
            # These are production-level errors that shouldn't fallback
            logger.error(f"Production HCL2 parsing failed: {e}")
            raise
        except Exception as e:
            logger.warning(f"HCL2 parsing failed: {e}, falling back to regex")
            return self._parse_with_regex_fallback(content)

    def _convert_hcl2_to_internal_format(self, parsed_data: Dict[str, Any]):
        """Convert HCL2 parsed data to internal format."""
        # Convert resources
        for resource_data in parsed_data.get("resources", []):
            resource = TerraformResource(
                type=resource_data["type"],
                name=resource_data["name"],
                line_start=resource_data["line_start"],
                line_end=resource_data["line_end"],
                content=resource_data["content"],
                attributes=resource_data["attributes"],
            )
            self.resources.append(resource)

        # Convert modules
        for module_data in parsed_data.get("modules", []):
            module = TerraformModule(
                name=module_data["name"],
                source=module_data["source"],
                line_start=module_data["line_start"],
                line_end=module_data["line_end"],
                content=module_data["content"],
                variables=module_data["variables"],
            )
            self.modules.append(module)

        # Convert variables
        for var_data in parsed_data.get("variables", []):
            variable = TerraformVariable(
                name=var_data["name"],
                type=var_data.get("type"),
                default=var_data.get("default"),
                description=var_data.get("description"),
                line_start=var_data["line_start"],
                line_end=var_data["line_end"],
            )
            self.variables.append(variable)

        # Convert outputs
        for output_data in parsed_data.get("outputs", []):
            output = TerraformOutput(
                name=output_data["name"],
                value=output_data["value"],
                description=output_data.get("description"),
                sensitive=output_data.get("sensitive", False),
                line_start=output_data["line_start"],
                line_end=output_data["line_end"],
            )
            self.outputs.append(output)

        # Convert providers
        self.providers = parsed_data.get("providers", [])

    def get_parser_info(self) -> Dict[str, Any]:
        """Get information about the current parser configuration."""
        return {
            "strategy": self.parser_strategy,
            "tree_sitter_available": TREE_SITTER_AVAILABLE,
            "hcl2_available": self.hcl_parser.is_available(),
            "active_parser": self.parser_strategy,
            "fallback_available": True,  # regex is always available
        }

    def _parse_with_tree_sitter(self, content: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Parse using tree-sitter for accurate parsing."""
        try:
            # Parse the content
            tree = self.tree_sitter_parser.parse(bytes(content, "utf8"))
            root_node = tree.root_node

            # Extract different types of blocks
            self._extract_blocks_from_tree(root_node, content)

            return {
                "resources": [self._resource_to_dict(r) for r in self.resources],
                "modules": [self._module_to_dict(m) for m in self.modules],
                "variables": [self._variable_to_dict(v) for v in self.variables],
                "outputs": [self._output_to_dict(o) for o in self.outputs],
                "providers": self.providers,
            }

        except Exception as e:
            logger.warning(
                f"Tree-sitter parsing failed: {e}, falling back to HCL2 or regex"
            )
            if self.hcl_parser.is_available():
                return self._parse_with_hcl2(content, file_path)
            else:
                return self._parse_with_regex_fallback(content)

    def _extract_blocks_from_tree(self, node, content: str):
        """Extract Terraform blocks from tree-sitter AST."""
        lines = content.split("\n")

        def traverse(node):
            # Check node type and extract accordingly
            if node.type == "block":
                self._process_block_node(node, lines, content)

            # Recursively traverse children
            for child in node.children:
                traverse(child)

        traverse(node)

    def _process_block_node(self, node, lines: List[str], content: str):
        """Process a block node from tree-sitter."""
        try:
            # Get block type (resource, module, variable, etc.)
            block_type = None
            block_labels = []

            for child in node.children:
                if child.type == "identifier" and not block_type:
                    block_type = self._get_node_text(child, content)
                elif child.type == "string_literal":
                    # Remove quotes from string literals
                    label = self._get_node_text(child, content).strip("\"'")
                    block_labels.append(label)

            if not block_type:
                return

            start_line = node.start_point[0]
            end_line = node.end_point[0]
            block_content = "\n".join(lines[start_line : end_line + 1])

            # Extract attributes from the block body
            attributes = self._extract_attributes_from_node(node, content)

            # Process based on block type
            if block_type == "resource" and len(block_labels) >= 2:
                resource = TerraformResource(
                    type=block_labels[0],
                    name=block_labels[1],
                    line_start=start_line + 1,
                    line_end=end_line + 1,
                    content=block_content,
                    attributes=attributes,
                )
                self.resources.append(resource)

            elif block_type == "module" and len(block_labels) >= 1:
                module = TerraformModule(
                    name=block_labels[0],
                    source=attributes.get("source", ""),
                    line_start=start_line + 1,
                    line_end=end_line + 1,
                    content=block_content,
                    variables=attributes,
                )
                self.modules.append(module)

            elif block_type == "variable" and len(block_labels) >= 1:
                variable = TerraformVariable(
                    name=block_labels[0],
                    type=attributes.get("type"),
                    default=attributes.get("default"),
                    description=attributes.get("description"),
                    line_start=start_line + 1,
                    line_end=end_line + 1,
                )
                self.variables.append(variable)

            elif block_type == "output" and len(block_labels) >= 1:
                output = TerraformOutput(
                    name=block_labels[0],
                    value=attributes.get("value", ""),
                    description=attributes.get("description"),
                    sensitive=attributes.get("sensitive", False),
                    line_start=start_line + 1,
                    line_end=end_line + 1,
                )
                self.outputs.append(output)

            elif block_type == "provider" and len(block_labels) >= 1:
                provider = {
                    "name": block_labels[0],
                    "line_start": start_line + 1,
                    "line_end": end_line + 1,
                    "attributes": attributes,
                }
                self.providers.append(provider)

        except Exception as e:
            logger.error(f"Error processing block node: {e}")

    def _get_node_text(self, node, content: str) -> str:
        """Get text content of a tree-sitter node."""
        return content[node.start_byte : node.end_byte]

    def _extract_attributes_from_node(self, node, content: str) -> Dict[str, Any]:
        """Extract attributes from a block node."""
        attributes = {}

        def find_assignments(node):
            if node.type == "assignment":
                # Get key and value
                key = None
                value = None

                for child in node.children:
                    if child.type == "identifier" and not key:
                        key = self._get_node_text(child, content)
                    elif child.type in [
                        "string_literal",
                        "number_literal",
                        "boolean_literal",
                    ]:
                        value = self._get_node_text(child, content).strip("\"'")
                    elif child.type == "expression":
                        value = self._get_node_text(child, content)

                if key and value is not None:
                    attributes[key] = value

            # Recursively search children
            for child in node.children:
                find_assignments(child)

        find_assignments(node)
        return attributes

    def _parse_with_regex_fallback(self, content: str) -> Dict[str, Any]:
        """Fallback regex-based parsing when tree-sitter is not available."""
        lines = content.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if line.startswith("resource "):
                i = self._parse_resource_regex(lines, i)
            elif line.startswith("module "):
                i = self._parse_module_regex(lines, i)
            elif line.startswith("variable "):
                i = self._parse_variable_regex(lines, i)
            elif line.startswith("output "):
                i = self._parse_output_regex(lines, i)
            elif line.startswith("provider "):
                i = self._parse_provider_regex(lines, i)
            else:
                i += 1

        return {
            "resources": [self._resource_to_dict(r) for r in self.resources],
            "modules": [self._module_to_dict(m) for m in self.modules],
            "variables": [self._variable_to_dict(v) for v in self.variables],
            "outputs": [self._output_to_dict(o) for o in self.outputs],
            "providers": self.providers,
        }

    def _reset(self):
        """Reset parser state."""
        self.resources.clear()
        self.modules.clear()
        self.variables.clear()
        self.outputs.clear()
        self.providers.clear()

    # Regex-based fallback methods (keeping the original implementation)
    def _parse_resource_regex(self, lines: List[str], start_idx: int) -> int:
        """Parse a Terraform resource block using regex."""
        import re

        line = lines[start_idx].strip()

        # Extract resource type and name
        match = re.match(r'resource\s+"([^"]+)"\s+"([^"]+)"\s*{?', line)
        if not match:
            return start_idx + 1

        resource_type, resource_name = match.groups()

        # Find the end of the resource block
        end_idx = self._find_block_end(lines, start_idx)

        # Extract content and attributes
        content = "\n".join(lines[start_idx : end_idx + 1])
        attributes = self._extract_attributes_regex(lines[start_idx + 1 : end_idx])

        resource = TerraformResource(
            type=resource_type,
            name=resource_name,
            line_start=start_idx + 1,
            line_end=end_idx + 1,
            content=content,
            attributes=attributes,
        )

        self.resources.append(resource)
        return end_idx + 1

    def _parse_module_regex(self, lines: List[str], start_idx: int) -> int:
        """Parse a Terraform module block using regex."""
        import re

        line = lines[start_idx].strip()

        # Extract module name
        match = re.match(r'module\s+"([^"]+)"\s*{?', line)
        if not match:
            return start_idx + 1

        module_name = match.group(1)

        # Find the end of the module block
        end_idx = self._find_block_end(lines, start_idx)

        # Extract content and variables
        content = "\n".join(lines[start_idx : end_idx + 1])
        variables = self._extract_attributes_regex(lines[start_idx + 1 : end_idx])

        # Extract source
        source = variables.get("source", "")

        module = TerraformModule(
            name=module_name,
            source=source,
            line_start=start_idx + 1,
            line_end=end_idx + 1,
            content=content,
            variables=variables,
        )

        self.modules.append(module)
        return end_idx + 1

    def _parse_variable_regex(self, lines: List[str], start_idx: int) -> int:
        """Parse a Terraform variable block using regex."""
        import re

        line = lines[start_idx].strip()

        # Extract variable name
        match = re.match(r'variable\s+"([^"]+)"\s*{?', line)
        if not match:
            return start_idx + 1

        var_name = match.group(1)

        # Find the end of the variable block
        end_idx = self._find_block_end(lines, start_idx)

        # Extract attributes
        attributes = self._extract_attributes_regex(lines[start_idx + 1 : end_idx])

        variable = TerraformVariable(
            name=var_name,
            type=attributes.get("type"),
            default=attributes.get("default"),
            description=attributes.get("description"),
            line_start=start_idx + 1,
            line_end=end_idx + 1,
        )

        self.variables.append(variable)
        return end_idx + 1

    def _parse_output_regex(self, lines: List[str], start_idx: int) -> int:
        """Parse a Terraform output block using regex."""
        import re

        line = lines[start_idx].strip()

        # Extract output name
        match = re.match(r'output\s+"([^"]+)"\s*{?', line)
        if not match:
            return start_idx + 1

        output_name = match.group(1)

        # Find the end of the output block
        end_idx = self._find_block_end(lines, start_idx)

        # Extract attributes
        attributes = self._extract_attributes_regex(lines[start_idx + 1 : end_idx])

        output = TerraformOutput(
            name=output_name,
            value=attributes.get("value", ""),
            description=attributes.get("description"),
            sensitive=attributes.get("sensitive", False),
            line_start=start_idx + 1,
            line_end=end_idx + 1,
        )

        self.outputs.append(output)
        return end_idx + 1

    def _parse_provider_regex(self, lines: List[str], start_idx: int) -> int:
        """Parse a Terraform provider block using regex."""
        import re

        line = lines[start_idx].strip()

        # Extract provider name
        match = re.match(r'provider\s+"([^"]+)"\s*{?', line)
        if not match:
            return start_idx + 1

        provider_name = match.group(1)

        # Find the end of the provider block
        end_idx = self._find_block_end(lines, start_idx)

        # Extract attributes
        attributes = self._extract_attributes_regex(lines[start_idx + 1 : end_idx])

        provider = {
            "name": provider_name,
            "line_start": start_idx + 1,
            "line_end": end_idx + 1,
            "attributes": attributes,
        }

        self.providers.append(provider)
        return end_idx + 1

    def _find_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find the end of a Terraform block."""
        brace_count = 0
        found_opening = False

        for i in range(start_idx, len(lines)):
            line = lines[i].strip()

            # Count braces
            for char in line:
                if char == "{":
                    brace_count += 1
                    found_opening = True
                elif char == "}":
                    brace_count -= 1

            # If we've found the opening brace and count is back to 0
            if found_opening and brace_count == 0:
                return i

        return len(lines) - 1

    def _extract_attributes_regex(self, lines: List[str]) -> Dict[str, Any]:
        """Extract attributes from Terraform block content."""
        attributes = {}

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Simple attribute extraction (key = value)
            if "=" in line:
                parts = line.split("=", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().rstrip(",")

                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    attributes[key] = value

        return attributes

    def _resource_to_dict(self, resource: TerraformResource) -> Dict[str, Any]:
        """Convert TerraformResource to dictionary."""
        return {
            "type": resource.type,
            "name": resource.name,
            "line_start": resource.line_start,
            "line_end": resource.line_end,
            "content": resource.content,
            "attributes": resource.attributes,
        }

    def _module_to_dict(self, module: TerraformModule) -> Dict[str, Any]:
        """Convert TerraformModule to dictionary."""
        return {
            "name": module.name,
            "source": module.source,
            "line_start": module.line_start,
            "line_end": module.line_end,
            "content": module.content,
            "variables": module.variables,
        }

    def _variable_to_dict(self, variable: TerraformVariable) -> Dict[str, Any]:
        """Convert TerraformVariable to dictionary."""
        return {
            "name": variable.name,
            "type": variable.type,
            "default": variable.default,
            "description": variable.description,
            "line_start": variable.line_start,
            "line_end": variable.line_end,
        }

    def _output_to_dict(self, output: TerraformOutput) -> Dict[str, Any]:
        """Convert TerraformOutput to dictionary."""
        return {
            "name": output.name,
            "value": output.value,
            "description": output.description,
            "sensitive": output.sensitive,
            "line_start": output.line_start,
            "line_end": output.line_end,
        }
