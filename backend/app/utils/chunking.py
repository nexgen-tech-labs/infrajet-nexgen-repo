"""
Text chunking utilities for Terraform files.
"""
import re
from typing import List, Dict, Any, Iterator, Tuple
from pathlib import Path
from logconfig.logger import get_logger

logger = get_logger()


class TerraformChunker:
    """Chunker specifically designed for Terraform/HCL files."""
    
    def __init__(self, max_chunk_size: int = 400, overlap_size: int = 60):
        """
        Initialize Terraform chunker.
        
        Args:
            max_chunk_size: Maximum number of tokens per chunk
            overlap_size: Number of tokens to overlap between chunks
        """
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
    
    def chunk_terraform_content(self, content: str, file_path: str = "", parsed_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Chunk Terraform content into semantically meaningful pieces.
        
        Args:
            content: Raw Terraform file content
            file_path: Path to the file (for metadata)
            parsed_data: Optional parsed Terraform data from tree-sitter
            
        Returns:
            List of chunk dictionaries with content and metadata
        """
        chunks = []
        
        try:
            # Strategy 1: Use parsed data if available (preferred)
            if parsed_data and self._has_terraform_blocks(parsed_data):
                chunks.extend(self._chunk_by_terraform_blocks(content, file_path, parsed_data))
            
            # Strategy 2: Fallback to HCL block detection
            if not chunks:
                chunks.extend(self._chunk_by_hcl_blocks(content, file_path))
            
            # Strategy 3: Final fallback to line-based chunking
            if not chunks:
                chunks.extend(self._chunk_by_lines(content, file_path))
            
            # Post-process chunks
            chunks = self._post_process_chunks(chunks)
            
            logger.info(f"Created {len(chunks)} chunks for {file_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error chunking Terraform content: {e}")
            # Emergency fallback
            return self._chunk_by_lines(content, file_path)
    
    def _has_terraform_blocks(self, parsed_data: Dict[str, Any]) -> bool:
        """Check if parsed data contains Terraform blocks."""
        terraform_keys = ['resources', 'variables', 'outputs', 'modules', 'providers', 'data_sources']
        return any(key in parsed_data and parsed_data[key] for key in terraform_keys)
    
    def _chunk_by_terraform_blocks(self, content: str, file_path: str, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk content based on parsed Terraform blocks."""
        chunks = []
        lines = content.splitlines()
        
        # Process different types of Terraform blocks
        block_types = [
            ('resources', 'resource'),
            ('variables', 'variable'),
            ('outputs', 'output'),
            ('modules', 'module'),
            ('providers', 'provider'),
            ('data_sources', 'data'),
            ('locals', 'locals'),
            ('terraform_blocks', 'terraform')
        ]
        
        for block_key, block_type in block_types:
            if block_key in parsed_data:
                blocks = parsed_data[block_key]
                if isinstance(blocks, list):
                    for block in blocks:
                        chunk = self._create_block_chunk(block, lines, file_path, block_type)
                        if chunk:
                            chunks.append(chunk)
                elif isinstance(blocks, dict):
                    for block_name, block_data in blocks.items():
                        chunk = self._create_dict_block_chunk(block_name, block_data, lines, file_path, block_type)
                        if chunk:
                            chunks.append(chunk)
        
        return chunks
    
    def _create_block_chunk(self, block: Dict[str, Any], lines: List[str], file_path: str, block_type: str) -> Dict[str, Any]:
        """Create a chunk from a parsed Terraform block."""
        try:
            start_line = block.get('start_line', 0)
            end_line = block.get('end_line', len(lines))
            
            # Extract content
            block_lines = lines[start_line:end_line + 1]
            content = '\n'.join(block_lines)
            
            # Create metadata
            metadata = {
                'file_path': file_path,
                'chunk_type': 'terraform_block',
                'block_type': block_type,
                'start_line': start_line,
                'end_line': end_line,
                'language': 'terraform'
            }
            
            # Add block-specific metadata
            if 'name' in block:
                metadata['block_name'] = block['name']
            if 'type' in block:
                metadata['resource_type'] = block['type']
            if 'attributes' in block:
                metadata['has_attributes'] = len(block['attributes']) > 0
            
            return {
                'content': content,
                'metadata': metadata,
                'token_count': self._estimate_token_count(content)
            }
            
        except Exception as e:
            logger.warning(f"Failed to create block chunk: {e}")
            return None
    
    def _create_dict_block_chunk(self, block_name: str, block_data: Dict[str, Any], lines: List[str], file_path: str, block_type: str) -> Dict[str, Any]:
        """Create a chunk from a dictionary-style block."""
        try:
            start_line = block_data.get('start_line', 0)
            end_line = block_data.get('end_line', len(lines))
            
            # Extract content
            block_lines = lines[start_line:end_line + 1]
            content = '\n'.join(block_lines)
            
            # Create metadata
            metadata = {
                'file_path': file_path,
                'chunk_type': 'terraform_block',
                'block_type': block_type,
                'block_name': block_name,
                'start_line': start_line,
                'end_line': end_line,
                'language': 'terraform'
            }
            
            return {
                'content': content,
                'metadata': metadata,
                'token_count': self._estimate_token_count(content)
            }
            
        except Exception as e:
            logger.warning(f"Failed to create dict block chunk: {e}")
            return None
    
    def _chunk_by_hcl_blocks(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk content by detecting HCL blocks using regex."""
        chunks = []
        lines = content.splitlines()
        
        # Regex to match HCL block starts
        block_pattern = re.compile(r'^(resource|variable|output|module|provider|data|locals|terraform)\s+')
        
        current_block_start = None
        current_block_type = None
        brace_count = 0
        
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            
            # Check for block start
            match = block_pattern.match(stripped_line)
            if match and brace_count == 0:
                # Save previous block if exists
                if current_block_start is not None:
                    chunk = self._create_line_range_chunk(
                        lines, current_block_start, i - 1, file_path, current_block_type
                    )
                    if chunk:
                        chunks.append(chunk)
                
                current_block_start = i
                current_block_type = match.group(1)
            
            # Count braces to track block boundaries
            brace_count += stripped_line.count('{') - stripped_line.count('}')
            
            # If we're at the end of a block
            if current_block_start is not None and brace_count == 0 and '{' in stripped_line:
                chunk = self._create_line_range_chunk(
                    lines, current_block_start, i, file_path, current_block_type
                )
                if chunk:
                    chunks.append(chunk)
                
                current_block_start = None
                current_block_type = None
        
        # Handle final block
        if current_block_start is not None:
            chunk = self._create_line_range_chunk(
                lines, current_block_start, len(lines) - 1, file_path, current_block_type
            )
            if chunk:
                chunks.append(chunk)
        
        return chunks
    
    def _create_line_range_chunk(self, lines: List[str], start_line: int, end_line: int, file_path: str, block_type: str = None) -> Dict[str, Any]:
        """Create a chunk from a line range."""
        try:
            block_lines = lines[start_line:end_line + 1]
            content = '\n'.join(block_lines)
            
            if not content.strip():
                return None
            
            metadata = {
                'file_path': file_path,
                'chunk_type': 'hcl_block' if block_type else 'line_range',
                'start_line': start_line,
                'end_line': end_line,
                'language': 'terraform'
            }
            
            if block_type:
                metadata['block_type'] = block_type
            
            return {
                'content': content,
                'metadata': metadata,
                'token_count': self._estimate_token_count(content)
            }
            
        except Exception as e:
            logger.warning(f"Failed to create line range chunk: {e}")
            return None
    
    def _chunk_by_lines(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback chunking by lines with overlap."""
        chunks = []
        lines = content.splitlines()
        
        if not lines:
            return chunks
        
        # Estimate lines per chunk based on token count
        avg_tokens_per_line = max(1, self._estimate_token_count(content) // len(lines))
        lines_per_chunk = max(1, self.max_chunk_size // avg_tokens_per_line)
        overlap_lines = max(1, self.overlap_size // avg_tokens_per_line)
        
        start_idx = 0
        chunk_idx = 0
        
        while start_idx < len(lines):
            end_idx = min(start_idx + lines_per_chunk, len(lines))
            
            chunk_lines = lines[start_idx:end_idx]
            content_chunk = '\n'.join(chunk_lines)
            
            if content_chunk.strip():
                metadata = {
                    'file_path': file_path,
                    'chunk_type': 'line_based',
                    'chunk_index': chunk_idx,
                    'start_line': start_idx,
                    'end_line': end_idx - 1,
                    'language': 'terraform'
                }
                
                chunks.append({
                    'content': content_chunk,
                    'metadata': metadata,
                    'token_count': self._estimate_token_count(content_chunk)
                })
                
                chunk_idx += 1
            
            # Move to next chunk with overlap
            start_idx = max(start_idx + lines_per_chunk - overlap_lines, start_idx + 1)
        
        return chunks
    
    def _post_process_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Post-process chunks to ensure quality."""
        processed_chunks = []
        
        for chunk in chunks:
            # Skip empty chunks
            if not chunk['content'].strip():
                continue
            
            # Split large chunks
            if chunk['token_count'] > self.max_chunk_size:
                sub_chunks = self._split_large_chunk(chunk)
                processed_chunks.extend(sub_chunks)
            else:
                processed_chunks.append(chunk)
        
        # Add chunk indices
        for i, chunk in enumerate(processed_chunks):
            chunk['metadata']['chunk_index'] = i
        
        return processed_chunks
    
    def _split_large_chunk(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Split a large chunk into smaller pieces."""
        content = chunk['content']
        lines = content.splitlines()
        
        if len(lines) <= 1:
            return [chunk]  # Can't split further
        
        # Split roughly in half
        mid_point = len(lines) // 2
        
        # Try to find a good split point (empty line or block boundary)
        split_point = mid_point
        for i in range(max(0, mid_point - 5), min(len(lines), mid_point + 5)):
            line = lines[i].strip()
            if not line or line == '}' or line.startswith('#'):
                split_point = i
                break
        
        # Create two chunks
        chunks = []
        
        # First chunk
        first_content = '\n'.join(lines[:split_point + 1])
        if first_content.strip():
            first_chunk = chunk.copy()
            first_chunk['content'] = first_content
            first_chunk['token_count'] = self._estimate_token_count(first_content)
            first_chunk['metadata'] = chunk['metadata'].copy()
            first_chunk['metadata']['split_part'] = 1
            chunks.append(first_chunk)
        
        # Second chunk
        second_content = '\n'.join(lines[split_point + 1:])
        if second_content.strip():
            second_chunk = chunk.copy()
            second_chunk['content'] = second_content
            second_chunk['token_count'] = self._estimate_token_count(second_content)
            second_chunk['metadata'] = chunk['metadata'].copy()
            second_chunk['metadata']['split_part'] = 2
            chunks.append(second_chunk)
        
        return chunks
    
    def _estimate_token_count(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Simple approximation: ~4 characters per token
        return max(1, len(text) // 4)