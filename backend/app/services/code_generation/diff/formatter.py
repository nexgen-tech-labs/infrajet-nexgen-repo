"""
Diff Formatter for Terraform Code Changes.

This module provides enhanced formatting capabilities for Terraform diff output,
including syntax highlighting, block-level formatting, and multiple output formats.
"""

import re
import html
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Any
from enum import Enum

from logconfig.logger import get_logger

logger = get_logger()


class OutputFormat(Enum):
    """Supported output formats for diff formatting."""
    TEXT = "text"
    HTML = "html"
    JSON = "json"
    MARKDOWN = "markdown"


class HighlightMode(Enum):
    """Syntax highlighting modes."""
    NONE = "none"
    BASIC = "basic"
    TERRAFORM = "terraform"


@dataclass
class FormatOptions:
    """Configuration options for diff formatting."""
    output_format: OutputFormat = OutputFormat.TEXT
    highlight_mode: HighlightMode = HighlightMode.TERRAFORM
    show_line_numbers: bool = True
    compact_mode: bool = False
    max_width: Optional[int] = None
    color_scheme: str = "default"
    include_metadata: bool = True
    block_level_formatting: bool = True


@dataclass
class FormattedDiff:
    """Formatted diff output with metadata."""
    content: str
    format_type: OutputFormat
    metadata: Dict[str, Any] = field(default_factory=dict)
    statistics: Dict[str, int] = field(default_factory=dict)


class TerraformDiffFormatter:
    """
    Enhanced formatter for Terraform diff output with multiple format support.

    Provides syntax highlighting, block-level formatting, and export capabilities
    for clear, readable diff presentation.
    """

    def __init__(self):
        """Initialize the diff formatter."""
        self.default_options = FormatOptions()
        self._init_color_schemes()
        self._init_terraform_patterns()
        logger.info("TerraformDiffFormatter initialized")

    def _init_color_schemes(self):
        """Initialize color schemes for highlighting."""
        self.color_schemes = {
            "default": {
                "addition": "\033[32m",  # Green
                "deletion": "\033[31m",  # Red
                "context": "\033[37m",   # White
                "header": "\033[36m",    # Cyan
                "reset": "\033[0m"
            },
            "dark": {
                "addition": "\033[92m",  # Bright green
                "deletion": "\033[91m",  # Bright red
                "context": "\033[90m",   # Dark gray
                "header": "\033[96m",    # Bright cyan
                "reset": "\033[0m"
            }
        }

    def _init_terraform_patterns(self):
        """Initialize regex patterns for Terraform syntax highlighting."""
        self.terraform_patterns = {
            "resource": re.compile(r'^(\s*)(resource\s+"[^"]+"\s+"[^"]+")'),
            "module": re.compile(r'^(\s*)(module\s+"[^"]+")'),
            "variable": re.compile(r'^(\s*)(variable\s+"[^"]+")'),
            "output": re.compile(r'^(\s*)(output\s+"[^"]+")'),
            "provider": re.compile(r'^(\s*)(provider\s+"[^"]+")'),
            "data": re.compile(r'^(\s*)(data\s+"[^"]+")'),
            "block_start": re.compile(r'^(\s*)\{'),
            "block_end": re.compile(r'^(\s*)\}'),
            "attribute": re.compile(r'^(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*='),
            "string": re.compile(r'"([^"]*)"'),
            "number": re.compile(r'\b\d+\b'),
            "boolean": re.compile(r'\b(true|false)\b'),
            "comment": re.compile(r'#.*$')
        }

    async def format_diff(
        self,
        diff_content: str,
        options: Optional[FormatOptions] = None
    ) -> FormattedDiff:
        """
        Format diff content according to specified options.

        Args:
            diff_content: Raw diff content to format
            options: Formatting options

        Returns:
            FormattedDiff with processed content and metadata
        """
        if options is None:
            options = self.default_options

        try:
            if options.output_format == OutputFormat.TEXT:
                formatted_content = self._format_text(diff_content, options)
            elif options.output_format == OutputFormat.HTML:
                formatted_content = self._format_html(diff_content, options)
            elif options.output_format == OutputFormat.JSON:
                formatted_content = self._format_json(diff_content, options)
            elif options.output_format == OutputFormat.MARKDOWN:
                formatted_content = self._format_markdown(diff_content, options)
            else:
                formatted_content = diff_content

            # Generate statistics
            statistics = self._generate_statistics(diff_content)

            # Create metadata
            metadata = {
                "format_type": options.output_format.value,
                "highlight_mode": options.highlight_mode.value,
                "compact_mode": options.compact_mode,
                "block_level_formatting": options.block_level_formatting
            }

            return FormattedDiff(
                content=formatted_content,
                format_type=options.output_format,
                metadata=metadata,
                statistics=statistics
            )

        except Exception as e:
            logger.error(f"Diff formatting failed: {e}")
            return FormattedDiff(
                content=diff_content,
                format_type=OutputFormat.TEXT,
                metadata={"error": str(e)}
            )

    def _format_text(self, diff_content: str, options: FormatOptions) -> str:
        """Format diff as plain text with optional highlighting."""
        lines = diff_content.splitlines()
        formatted_lines = []

        for i, line in enumerate(lines, 1):
            if options.show_line_numbers:
                line_num = f"{i:4d}: "
            else:
                line_num = ""

            if line.startswith('+') and not line.startswith('+++'):
                # Addition line
                if options.highlight_mode != HighlightMode.NONE:
                    colors = self.color_schemes.get(options.color_scheme, self.color_schemes["default"])
                    formatted_line = f"{colors['addition']}{line_num}{line}{colors['reset']}"
                else:
                    formatted_line = f"{line_num}{line}"
            elif line.startswith('-') and not line.startswith('---'):
                # Deletion line
                if options.highlight_mode != HighlightMode.NONE:
                    colors = self.color_schemes.get(options.color_scheme, self.color_schemes["default"])
                    formatted_line = f"{colors['deletion']}{line_num}{line}{colors['reset']}"
                else:
                    formatted_line = f"{line_num}{line}"
            elif line.startswith('@@'):
                # Hunk header
                if options.highlight_mode != HighlightMode.NONE:
                    colors = self.color_schemes.get(options.color_scheme, self.color_schemes["default"])
                    formatted_line = f"{colors['header']}{line_num}{line}{colors['reset']}"
                else:
                    formatted_line = f"{line_num}{line}"
            else:
                # Context line
                if options.highlight_mode != HighlightMode.NONE:
                    colors = self.color_schemes.get(options.color_scheme, self.color_schemes["default"])
                    formatted_line = f"{colors['context']}{line_num}{line}{colors['reset']}"
                else:
                    formatted_line = f"{line_num}{line}"

            # Apply Terraform syntax highlighting if enabled
            if options.highlight_mode == HighlightMode.TERRAFORM:
                formatted_line = self._apply_terraform_highlighting(formatted_line, options)

            formatted_lines.append(formatted_line)

        return '\n'.join(formatted_lines)

    def _format_html(self, diff_content: str, options: FormatOptions) -> str:
        """Format diff as HTML with CSS styling."""
        lines = diff_content.splitlines()
        html_lines = []

        # HTML header
        html_lines.append("<!DOCTYPE html>")
        html_lines.append("<html><head>")
        html_lines.append("<style>")
        html_lines.append(self._get_html_css(options.color_scheme))
        html_lines.append("</style>")
        html_lines.append("</head><body>")
        html_lines.append("<pre class='diff-container'>")

        for i, line in enumerate(lines, 1):
            line_num = f"<span class='line-number'>{i:4d}:</span> " if options.show_line_numbers else ""

            if line.startswith('+') and not line.startswith('+++'):
                css_class = "diff-addition"
                content = html.escape(line)
            elif line.startswith('-') and not line.startswith('---'):
                css_class = "diff-deletion"
                content = html.escape(line)
            elif line.startswith('@@'):
                css_class = "diff-header"
                content = html.escape(line)
            else:
                css_class = "diff-context"
                content = html.escape(line)

            # Apply Terraform highlighting
            if options.highlight_mode == HighlightMode.TERRAFORM:
                content = self._apply_terraform_html_highlighting(content)

            html_lines.append(f"<span class='{css_class}'>{line_num}{content}</span>")

        html_lines.append("</pre>")
        html_lines.append("</body></html>")

        return '\n'.join(html_lines)

    def _format_json(self, diff_content: str, options: FormatOptions) -> str:
        """Format diff as JSON structure."""
        import json

        lines = diff_content.splitlines()
        diff_data = {
            "format": "json",
            "lines": []
        }

        for i, line in enumerate(lines, 1):
            line_type = "context"
            if line.startswith('+') and not line.startswith('+++'):
                line_type = "addition"
            elif line.startswith('-') and not line.startswith('---'):
                line_type = "deletion"
            elif line.startswith('@@'):
                line_type = "header"

            diff_data["lines"].append({
                "number": i,
                "type": line_type,
                "content": line
            })

        return json.dumps(diff_data, indent=2)

    def _format_markdown(self, diff_content: str, options: FormatOptions) -> str:
        """Format diff as Markdown with code blocks."""
        lines = diff_content.splitlines()
        markdown_lines = ["```diff"]

        for line in lines:
            markdown_lines.append(line)

        markdown_lines.append("```")
        return '\n'.join(markdown_lines)

    def _apply_terraform_highlighting(self, line: str, options: FormatOptions) -> str:
        """Apply Terraform-specific syntax highlighting to a line."""
        if options.highlight_mode != HighlightMode.TERRAFORM:
            return line

        # Apply highlighting based on patterns
        highlighted = line

        # Highlight block declarations
        for pattern_name, pattern in self.terraform_patterns.items():
            if pattern_name in ["resource", "module", "variable", "output", "provider", "data"]:
                highlighted = pattern.sub(r'\1\033[1;34m\2\033[0m', highlighted)  # Bold blue

        # Highlight strings
        highlighted = self.terraform_patterns["string"].sub(r'"\033[32m\1\033[0m"', highlighted)

        # Highlight booleans
        highlighted = self.terraform_patterns["boolean"].sub(r'\033[33m\1\033[0m', highlighted)

        # Highlight comments
        highlighted = self.terraform_patterns["comment"].sub(r'\033[36m\1\033[0m', highlighted)

        return highlighted

    def _apply_terraform_html_highlighting(self, content: str) -> str:
        """Apply Terraform syntax highlighting for HTML output."""
        # Similar to text highlighting but with HTML tags
        highlighted = content

        # Highlight block declarations
        for pattern_name, pattern in self.terraform_patterns.items():
            if pattern_name in ["resource", "module", "variable", "output", "provider", "data"]:
                highlighted = pattern.sub(r'\1<span class="terraform-block">\2</span>', highlighted)

        # Highlight strings
        highlighted = self.terraform_patterns["string"].sub(r'<span class="terraform-string">"\1"</span>', highlighted)

        # Highlight booleans
        highlighted = self.terraform_patterns["boolean"].sub(r'<span class="terraform-boolean">\1</span>', highlighted)

        return highlighted

    def _get_html_css(self, color_scheme: str) -> str:
        """Get CSS styles for HTML diff output."""
        return """
        .diff-container {
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 12px;
            line-height: 1.4;
            background-color: #f8f8f8;
            padding: 10px;
            border-radius: 5px;
        }
        .diff-addition {
            background-color: #e6ffed;
            color: #22863a;
        }
        .diff-deletion {
            background-color: #ffeef0;
            color: #cb2431;
        }
        .diff-header {
            background-color: #f1f8ff;
            color: #0366d6;
            font-weight: bold;
        }
        .diff-context {
            color: #586069;
        }
        .line-number {
            color: #1b1f23;
            margin-right: 10px;
            user-select: none;
        }
        .terraform-block {
            color: #005cc5;
            font-weight: bold;
        }
        .terraform-string {
            color: #032f62;
        }
        .terraform-boolean {
            color: #d73a49;
            font-weight: bold;
        }
        """

    def _generate_statistics(self, diff_content: str) -> Dict[str, int]:
        """Generate statistics about the diff content."""
        lines = diff_content.splitlines()
        additions = 0
        deletions = 0
        context_lines = 0
        headers = 0

        for line in lines:
            if line.startswith('+') and not line.startswith('+++'):
                additions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1
            elif line.startswith('@@'):
                headers += 1
            else:
                context_lines += 1

        return {
            "total_lines": len(lines),
            "additions": additions,
            "deletions": deletions,
            "context_lines": context_lines,
            "headers": headers,
            "changes": additions + deletions
        }

    async def get_formatter_stats(self) -> Dict[str, Any]:
        """Get statistics about the diff formatter."""
        return {
            "status": "operational",
            "supported_formats": [fmt.value for fmt in OutputFormat],
            "highlight_modes": [mode.value for mode in HighlightMode],
            "color_schemes": list(self.color_schemes.keys()),
            "terraform_patterns": len(self.terraform_patterns)
        }