"""
Production-ready HCL parser using python-hcl2 library.

This module provides HCL (HashiCorp Configuration Language) parsing
capabilities using the python-hcl2 library with production-level features
including line number tracking, error handling, performance optimization,
caching, and validation.
"""

from typing import Dict, List, Optional, Any, Tuple
import json
import re
import time
import hashlib
import signal
from functools import lru_cache
from logconfig.logger import get_logger

logger = get_logger()


class HCLParser:
    """
    Production-ready parser using python-hcl2 library for robust HCL parsing.

    This parser provides the most reliable parsing for HCL/Terraform
    configurations by using the official python-hcl2 library with
    production-level features including line number tracking, error handling,
    performance optimization, and validation.
    """

    # Production limits
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_PARSE_TIME = 30  # 30 seconds
    CACHE_SIZE = 128  # Number of parsed files to cache

    def __init__(self):
        """Initialize the HCL parser with python-hcl2 if available."""
        self.hcl2 = None
        self._parse_cache = {}
        self._cache_timestamps = {}
        self._initialize_hcl2()

    def _initialize_hcl2(self):
        """Initialize python-hcl2 parser if available."""
        try:
            import hcl2

            self.hcl2 = hcl2
            logger.info("python-hcl2 parser initialized successfully")
        except ImportError:
            logger.warning("python-hcl2 not available, falling back to other parsers")
            self.hcl2 = None

    def parse_content(
        self, content: str, file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse HCL content using python-hcl2 with production-level features.

        Args:
            content: HCL content to parse
            file_path: Optional file path for caching and error reporting

        Returns:
            Parsed HCL structure with line numbers and validation

        Raises:
            ValueError: If content is invalid or parsing fails
            TimeoutError: If parsing takes too long
            MemoryError: If content is too large
        """
        if not self.hcl2:
            raise ImportError("python-hcl2 not available")

        # Production validations
        self._validate_content_size(content)

        # Check cache first
        cache_key = self._get_cache_key(content, file_path)
        if cache_key in self._parse_cache:
            logger.debug(f"Using cached parse result for {file_path or 'content'}")
            return self._parse_cache[cache_key]

        start_time = time.time()

        try:
            # Parse HCL content with timeout protection
            parsed = self._parse_with_timeout(content)

            # Validate parsed content structure
            if not isinstance(parsed, dict):
                logger.warning(f"Expected dict from HCL parser, got {type(parsed)}")
                parsed = {}

            # Extract line numbers from original content
            line_map = self._build_line_map(content)

            # Extract different types of blocks with line numbers
            result = {
                "resources": self._extract_resources(parsed, line_map, content),
                "modules": self._extract_modules(parsed, line_map, content),
                "variables": self._extract_variables(parsed, line_map, content),
                "outputs": self._extract_outputs(parsed, line_map, content),
                "providers": self._extract_providers(parsed, line_map, content),
                "data": self._extract_data_sources(parsed, line_map, content),
                "locals": self._extract_locals(parsed, line_map, content),
                "terraform": self._extract_terraform_blocks(parsed, line_map, content),
            }

            # Add metadata
            result["_metadata"] = {
                "parse_time": time.time() - start_time,
                "content_size": len(content),
                "line_count": len(content.split("\n")),
                "parser": "hcl2",
                "file_path": file_path,
            }

            # Cache result
            self._cache_result(cache_key, result)

            logger.info(
                f"Successfully parsed HCL content ({len(content)} chars) with "
                f"{len(result['resources'])} resources, {len(result['modules'])} modules, "
                f"{len(result['variables'])} variables, {len(result['outputs'])} outputs "
                f"in {result['_metadata']['parse_time']:.3f}s"
            )

            return result

        except TimeoutError:
            logger.error(
                f"HCL parsing timed out after {self.MAX_PARSE_TIME}s for {file_path or 'content'}"
            )
            raise
        except Exception as e:
            parse_time = time.time() - start_time
            logger.error(
                f"Failed to parse HCL content ({len(content)} chars) in {parse_time:.3f}s: {str(e)}"
            )
            raise ValueError(f"Failed to parse HCL content: {str(e)}")

    def _validate_content_size(self, content: str) -> None:
        """Validate content size for production limits."""
        content_size = len(content.encode("utf-8"))
        if content_size > self.MAX_FILE_SIZE:
            raise MemoryError(
                f"Content size ({content_size} bytes) exceeds maximum allowed size ({self.MAX_FILE_SIZE} bytes)"
            )

    def _get_cache_key(self, content: str, file_path: Optional[str]) -> str:
        """Generate cache key for content."""
        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        return f"{file_path or 'content'}:{content_hash}"

    def _parse_with_timeout(self, content: str) -> Dict[str, Any]:
        """Parse content with timeout protection."""
        try:
            # Try to use signal-based timeout (Unix systems)
            def timeout_handler(signum, frame):
                raise TimeoutError(
                    f"HCL parsing timed out after {self.MAX_PARSE_TIME} seconds"
                )

            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.MAX_PARSE_TIME)

            try:
                result = self.hcl2.loads(content)
                return result
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

        except (AttributeError, OSError):
            # Windows doesn't support SIGALRM, use basic parsing
            logger.debug("Signal-based timeout not available on this platform")
            return self.hcl2.loads(content)

    def _build_line_map(self, content: str) -> Dict[str, Tuple[int, int]]:
        """
        Build a map of block identifiers to line numbers.

        This analyzes the raw content to find line numbers for blocks
        since python-hcl2 doesn't provide this information.
        """
        line_map = {}
        lines = content.split("\n")

        # Patterns for different block types
        patterns = {
            "resource": re.compile(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"\s*{'),
            "module": re.compile(r'^\s*module\s+"([^"]+)"\s*{'),
            "variable": re.compile(r'^\s*variable\s+"([^"]+)"\s*{'),
            "output": re.compile(r'^\s*output\s+"([^"]+)"\s*{'),
            "provider": re.compile(r'^\s*provider\s+"([^"]+)"\s*{'),
            "data": re.compile(r'^\s*data\s+"([^"]+)"\s+"([^"]+)"\s*{'),
            "locals": re.compile(r"^\s*locals\s*{"),
            "terraform": re.compile(r"^\s*terraform\s*{"),
        }

        for line_num, line in enumerate(lines, 1):
            for block_type, pattern in patterns.items():
                match = pattern.match(line)
                if match:
                    # Find the end of this block
                    end_line = self._find_block_end_line(lines, line_num - 1)

                    if block_type in ["resource", "data"]:
                        # Resource and data have type and name
                        key = f"{block_type}:{match.group(1)}:{match.group(2)}"
                    elif block_type in ["module", "variable", "output", "provider"]:
                        # These have just a name
                        key = f"{block_type}:{match.group(1)}"
                    else:
                        # locals and terraform blocks
                        key = f"{block_type}:0"

                    line_map[key] = (line_num, end_line)
                    break

        return line_map

    def _find_block_end_line(self, lines: List[str], start_line: int) -> int:
        """Find the end line of a block starting at start_line."""
        brace_count = 0
        found_opening = False

        for i in range(start_line, len(lines)):
            line = lines[i]
            for char in line:
                if char == "{":
                    brace_count += 1
                    found_opening = True
                elif char == "}":
                    brace_count -= 1

            if found_opening and brace_count == 0:
                return i + 1

        return len(lines)

    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Cache parse result with size management."""
        # Clean old cache entries if needed
        if len(self._parse_cache) >= self.CACHE_SIZE:
            # Remove oldest entry
            oldest_key = min(
                self._cache_timestamps.keys(), key=lambda k: self._cache_timestamps[k]
            )
            del self._parse_cache[oldest_key]
            del self._cache_timestamps[oldest_key]

        self._parse_cache[cache_key] = result
        self._cache_timestamps[cache_key] = time.time()

    def _extract_resources(
        self, parsed: Dict[str, Any], line_map: Dict[str, Tuple[int, int]], content: str
    ) -> List[Dict[str, Any]]:
        """Extract resource blocks with line numbers."""
        resources = []

        resource_blocks = parsed.get("resource", [])
        logger.debug(
            f"Resource blocks found: {type(resource_blocks)}, content: {resource_blocks}"
        )

        if isinstance(resource_blocks, list):
            for resource_block in resource_blocks:
                if not isinstance(resource_block, dict):
                    logger.warning(
                        f"Expected dict in resource block, got {type(resource_block)}"
                    )
                    continue

                for resource_type, resource_instances in resource_block.items():
                    if not isinstance(resource_instances, dict):
                        logger.warning(
                            f"Expected dict for resource instances, got {type(resource_instances)}"
                        )
                        continue

                    for resource_name, resource_config in resource_instances.items():
                        try:
                            # Get line numbers from line map
                            line_key = f"resource:{resource_type}:{resource_name}"
                            line_start, line_end = line_map.get(line_key, (0, 0))

                            resources.append(
                                {
                                    "type": resource_type,
                                    "name": resource_name,
                                    "attributes": (
                                        resource_config
                                        if isinstance(resource_config, dict)
                                        else {}
                                    ),
                                    "line_start": line_start,
                                    "line_end": line_end,
                                    "content": (
                                        json.dumps(resource_config, indent=2)
                                        if resource_config
                                        else "{}"
                                    ),
                                }
                            )
                        except Exception as e:
                            logger.warning(
                                f"Error processing resource {resource_type}.{resource_name}: {e}"
                            )
        else:
            logger.warning(
                f"Expected list for resource blocks, got {type(resource_blocks)}"
            )

        return resources

    def _extract_modules(
        self, parsed: Dict[str, Any], line_map: Dict[str, Tuple[int, int]], content: str
    ) -> List[Dict[str, Any]]:
        """Extract module blocks with line numbers."""
        modules = []

        module_blocks = parsed.get("module", {})
        if not isinstance(module_blocks, dict):
            logger.warning(
                f"Expected dict for module blocks, got {type(module_blocks)}"
            )
            return modules

        for module_name, module_config in module_blocks.items():
            try:
                if not isinstance(module_config, dict):
                    logger.warning(
                        f"Expected dict for module config, got {type(module_config)}"
                    )
                    module_config = {}

                # Get line numbers from line map
                line_key = f"module:{module_name}"
                line_start, line_end = line_map.get(line_key, (0, 0))

                modules.append(
                    {
                        "name": module_name,
                        "source": module_config.get("source", ""),
                        "variables": module_config,
                        "line_start": line_start,
                        "line_end": line_end,
                        "content": json.dumps(module_config, indent=2),
                    }
                )
            except Exception as e:
                logger.warning(f"Error processing module {module_name}: {e}")

        return modules

    def _extract_variables(
        self, parsed: Dict[str, Any], line_map: Dict[str, Tuple[int, int]], content: str
    ) -> List[Dict[str, Any]]:
        """Extract variable blocks with line numbers."""
        variables = []

        variable_blocks = parsed.get("variable", [])
        if isinstance(variable_blocks, list):
            for variable_block in variable_blocks:
                if not isinstance(variable_block, dict):
                    logger.warning(
                        f"Expected dict in variable block, got {type(variable_block)}"
                    )
                    continue

                for var_name, var_config in variable_block.items():
                    try:
                        if not isinstance(var_config, dict):
                            logger.warning(
                                f"Expected dict for variable config, got {type(var_config)}"
                            )
                            var_config = {}

                        # Get line numbers from line map
                        line_key = f"variable:{var_name}"
                        line_start, line_end = line_map.get(line_key, (0, 0))

                        variables.append(
                            {
                                "name": var_name,
                                "type": var_config.get("type"),
                                "default": var_config.get("default"),
                                "description": var_config.get("description"),
                                "validation": var_config.get("validation"),
                                "sensitive": var_config.get("sensitive", False),
                                "line_start": line_start,
                                "line_end": line_end,
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Error processing variable {var_name}: {e}")
        else:
            logger.warning(
                f"Expected list for variable blocks, got {type(variable_blocks)}"
            )

        return variables

    def _extract_outputs(
        self, parsed: Dict[str, Any], line_map: Dict[str, Tuple[int, int]], content: str
    ) -> List[Dict[str, Any]]:
        """Extract output blocks with line numbers."""
        outputs = []

        output_blocks = parsed.get("output", [])
        if isinstance(output_blocks, list):
            for output_block in output_blocks:
                if not isinstance(output_block, dict):
                    logger.warning(
                        f"Expected dict in output block, got {type(output_block)}"
                    )
                    continue

                for output_name, output_config in output_block.items():
                    try:
                        if not isinstance(output_config, dict):
                            logger.warning(
                                f"Expected dict for output config, got {type(output_config)}"
                            )
                            output_config = {}

                        # Get line numbers from line map
                        line_key = f"output:{output_name}"
                        line_start, line_end = line_map.get(line_key, (0, 0))

                        outputs.append(
                            {
                                "name": output_name,
                                "value": output_config.get("value", ""),
                                "description": output_config.get("description"),
                                "sensitive": output_config.get("sensitive", False),
                                "depends_on": output_config.get("depends_on", []),
                                "line_start": line_start,
                                "line_end": line_end,
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Error processing output {output_name}: {e}")
        else:
            logger.warning(
                f"Expected list for output blocks, got {type(output_blocks)}"
            )

        return outputs

    def _extract_providers(
        self, parsed: Dict[str, Any], line_map: Dict[str, Tuple[int, int]], content: str
    ) -> List[Dict[str, Any]]:
        """Extract provider blocks with line numbers."""
        providers = []

        provider_blocks = parsed.get("provider", {})
        if not isinstance(provider_blocks, dict):
            logger.warning(
                f"Expected dict for provider blocks, got {type(provider_blocks)}"
            )
            return providers

        for provider_name, provider_configs in provider_blocks.items():
            try:
                # Get line numbers from line map
                line_key = f"provider:{provider_name}"
                line_start, line_end = line_map.get(line_key, (0, 0))

                # Handle both single provider and multiple provider configurations
                if isinstance(provider_configs, list):
                    for i, provider_config in enumerate(provider_configs):
                        if not isinstance(provider_config, dict):
                            logger.warning(
                                f"Expected dict for provider config, got {type(provider_config)}"
                            )
                            provider_config = {}

                        providers.append(
                            {
                                "name": provider_name,
                                "alias": provider_config.get("alias"),
                                "attributes": provider_config,
                                "line_start": line_start,
                                "line_end": line_end,
                            }
                        )
                elif isinstance(provider_configs, dict):
                    providers.append(
                        {
                            "name": provider_name,
                            "alias": provider_configs.get("alias"),
                            "attributes": provider_configs,
                            "line_start": line_start,
                            "line_end": line_end,
                        }
                    )
                else:
                    logger.warning(
                        f"Unexpected provider config type for {provider_name}: {type(provider_configs)}"
                    )
            except Exception as e:
                logger.warning(f"Error processing provider {provider_name}: {e}")

        return providers

    def _extract_data_sources(
        self, parsed: Dict[str, Any], line_map: Dict[str, Tuple[int, int]], content: str
    ) -> List[Dict[str, Any]]:
        """Extract data source blocks with line numbers."""
        data_sources = []

        data_blocks = parsed.get("data", {})
        if not isinstance(data_blocks, dict):
            logger.warning(f"Expected dict for data blocks, got {type(data_blocks)}")
            return data_sources

        for data_type, data_instances in data_blocks.items():
            try:
                if not isinstance(data_instances, dict):
                    logger.warning(
                        f"Expected dict for data instances, got {type(data_instances)}"
                    )
                    continue

                for data_name, data_config in data_instances.items():
                    try:
                        # Get line numbers from line map
                        line_key = f"data:{data_type}:{data_name}"
                        line_start, line_end = line_map.get(line_key, (0, 0))

                        data_sources.append(
                            {
                                "type": data_type,
                                "name": data_name,
                                "attributes": (
                                    data_config if isinstance(data_config, dict) else {}
                                ),
                                "line_start": line_start,
                                "line_end": line_end,
                                "content": (
                                    json.dumps(data_config, indent=2)
                                    if data_config
                                    else "{}"
                                ),
                            }
                        )
                    except Exception as e:
                        logger.warning(
                            f"Error processing data source {data_type}.{data_name}: {e}"
                        )
            except Exception as e:
                logger.warning(f"Error processing data type {data_type}: {e}")

        return data_sources

    def _extract_locals(
        self, parsed: Dict[str, Any], line_map: Dict[str, Tuple[int, int]], content: str
    ) -> List[Dict[str, Any]]:
        """Extract locals blocks with line numbers."""
        locals_list = []

        locals_blocks = parsed.get("locals", [])
        if isinstance(locals_blocks, list):
            for i, locals_block in enumerate(locals_blocks):
                # Get line numbers from line map
                line_key = f"locals:0"
                line_start, line_end = line_map.get(line_key, (0, 0))

                locals_list.append(
                    {
                        "index": i,
                        "values": locals_block,
                        "line_start": line_start,
                        "line_end": line_end,
                    }
                )
        elif isinstance(locals_blocks, dict):
            # Get line numbers from line map
            line_key = f"locals:0"
            line_start, line_end = line_map.get(line_key, (0, 0))

            locals_list.append(
                {
                    "index": 0,
                    "values": locals_blocks,
                    "line_start": line_start,
                    "line_end": line_end,
                }
            )

        return locals_list

    def _extract_terraform_blocks(
        self, parsed: Dict[str, Any], line_map: Dict[str, Tuple[int, int]], content: str
    ) -> List[Dict[str, Any]]:
        """Extract terraform configuration blocks with line numbers."""
        terraform_blocks = []

        terraform_config = parsed.get("terraform", [])
        if isinstance(terraform_config, list):
            for i, config in enumerate(terraform_config):
                # Get line numbers from line map
                line_key = f"terraform:0"
                line_start, line_end = line_map.get(line_key, (0, 0))

                terraform_blocks.append(
                    {
                        "index": i,
                        "required_version": config.get("required_version"),
                        "required_providers": config.get("required_providers", {}),
                        "backend": config.get("backend", {}),
                        "experiments": config.get("experiments", []),
                        "line_start": line_start,
                        "line_end": line_end,
                    }
                )
        elif isinstance(terraform_config, dict):
            # Get line numbers from line map
            line_key = f"terraform:0"
            line_start, line_end = line_map.get(line_key, (0, 0))

            terraform_blocks.append(
                {
                    "index": 0,
                    "required_version": terraform_config.get("required_version"),
                    "required_providers": terraform_config.get(
                        "required_providers", {}
                    ),
                    "backend": terraform_config.get("backend", {}),
                    "experiments": terraform_config.get("experiments", []),
                    "line_start": line_start,
                    "line_end": line_end,
                }
            )

        return terraform_blocks

    def is_available(self) -> bool:
        """Check if HCL2 parser is available."""
        return self.hcl2 is not None

    def clear_cache(self) -> None:
        """Clear the parse cache."""
        self._parse_cache.clear()
        self._cache_timestamps.clear()
        logger.info("Parse cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._parse_cache),
            "max_cache_size": self.CACHE_SIZE,
            "cache_hit_ratio": getattr(self, "_cache_hits", 0)
            / max(getattr(self, "_cache_requests", 1), 1),
        }
