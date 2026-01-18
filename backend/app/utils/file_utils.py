"""
File utilities for processing Terraform files.
"""
import os
from pathlib import Path
from typing import Iterator, List, Set, Optional
from logconfig.logger import get_logger

logger = get_logger()


class TerraformFileWalker:
    """Utility for walking and filtering Terraform files."""
    
    def __init__(self, allowed_extensions: tuple = (".tf", ".tfvars", ".hcl")):
        """
        Initialize file walker.
        
        Args:
            allowed_extensions: Tuple of allowed file extensions
        """
        self.allowed_extensions = allowed_extensions
        self.excluded_dirs = {
            '.git', '.terraform', 'node_modules', '__pycache__', 
            '.vscode', '.idea', 'dist', 'build', 'target'
        }
        self.excluded_files = {
            '.DS_Store', 'Thumbs.db', '.gitignore', '.terraformignore'
        }
    
    def walk_directory(self, directory_path: str, recursive: bool = True, max_files: int = 1000) -> Iterator[Path]:
        """
        Walk directory and yield Terraform files.
        
        Args:
            directory_path: Root directory to walk
            recursive: Whether to walk subdirectories
            max_files: Maximum number of files to process
            
        Yields:
            Path objects for Terraform files
        """
        root_path = Path(directory_path).resolve()
        
        if not root_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        if not root_path.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")
        
        files_found = 0
        
        try:
            if recursive:
                for file_path in self._walk_recursive(root_path):
                    if files_found >= max_files:
                        logger.warning(f"Reached maximum file limit ({max_files}). Stopping.")
                        break
                    
                    if self._is_terraform_file(file_path):
                        yield file_path
                        files_found += 1
            else:
                for file_path in root_path.iterdir():
                    if files_found >= max_files:
                        logger.warning(f"Reached maximum file limit ({max_files}). Stopping.")
                        break
                    
                    if file_path.is_file() and self._is_terraform_file(file_path):
                        yield file_path
                        files_found += 1
        
        except PermissionError as e:
            logger.error(f"Permission denied accessing directory: {e}")
            raise
        except Exception as e:
            logger.error(f"Error walking directory {directory_path}: {e}")
            raise
    
    def _walk_recursive(self, root_path: Path) -> Iterator[Path]:
        """Recursively walk directory tree."""
        try:
            for item in root_path.iterdir():
                if item.is_file():
                    yield item
                elif item.is_dir() and not self._is_excluded_directory(item):
                    yield from self._walk_recursive(item)
        except PermissionError:
            logger.warning(f"Permission denied accessing: {root_path}")
        except Exception as e:
            logger.warning(f"Error accessing {root_path}: {e}")
    
    def _is_terraform_file(self, file_path: Path) -> bool:
        """Check if file is a Terraform file."""
        if not file_path.is_file():
            return False
        
        if file_path.name in self.excluded_files:
            return False
        
        if file_path.suffix.lower() in self.allowed_extensions:
            return True
        
        # Check for files without extensions that might be Terraform
        if not file_path.suffix and file_path.name.lower() in ('terraform', 'terragrunt'):
            return True
        
        return False
    
    def _is_excluded_directory(self, dir_path: Path) -> bool:
        """Check if directory should be excluded."""
        return dir_path.name in self.excluded_dirs or dir_path.name.startswith('.')
    
    def get_file_info(self, file_path: Path) -> dict:
        """Get information about a Terraform file."""
        try:
            stat = file_path.stat()
            return {
                'path': str(file_path),
                'name': file_path.name,
                'extension': file_path.suffix,
                'size_bytes': stat.st_size,
                'size_kb': round(stat.st_size / 1024, 2),
                'modified_time': stat.st_mtime,
                'is_readable': os.access(file_path, os.R_OK)
            }
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return {
                'path': str(file_path),
                'name': file_path.name,
                'extension': file_path.suffix,
                'error': str(e)
            }
    
    def read_file_content(self, file_path: Path, encoding: str = 'utf-8') -> str:
        """
        Read file content safely.
        
        Args:
            file_path: Path to file
            encoding: File encoding
            
        Returns:
            File content as string
        """
        try:
            return file_path.read_text(encoding=encoding, errors='ignore')
        except UnicodeDecodeError:
            # Try with different encodings
            for fallback_encoding in ['latin-1', 'cp1252', 'utf-16']:
                try:
                    return file_path.read_text(encoding=fallback_encoding, errors='ignore')
                except UnicodeDecodeError:
                    continue
            
            # Final fallback - read as binary and decode with errors ignored
            logger.warning(f"Using binary read with error handling for {file_path}")
            return file_path.read_bytes().decode('utf-8', errors='ignore')
        
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise
    
    def validate_file_size(self, file_path: Path, max_size_mb: float = 10.0) -> bool:
        """
        Validate file size is within limits.
        
        Args:
            file_path: Path to file
            max_size_mb: Maximum file size in MB
            
        Returns:
            True if file size is acceptable
        """
        try:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > max_size_mb:
                logger.warning(f"File {file_path} is too large: {size_mb:.2f}MB > {max_size_mb}MB")
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking file size for {file_path}: {e}")
            return False
    
    def get_directory_stats(self, directory_path: str, recursive: bool = True) -> dict:
        """
        Get statistics about Terraform files in directory.
        
        Args:
            directory_path: Directory to analyze
            recursive: Whether to include subdirectories
            
        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_files': 0,
            'total_size_bytes': 0,
            'file_types': {},
            'largest_file': None,
            'largest_file_size': 0,
            'errors': []
        }
        
        try:
            for file_path in self.walk_directory(directory_path, recursive=recursive):
                try:
                    file_info = self.get_file_info(file_path)
                    
                    if 'error' in file_info:
                        stats['errors'].append(f"{file_path}: {file_info['error']}")
                        continue
                    
                    stats['total_files'] += 1
                    stats['total_size_bytes'] += file_info['size_bytes']
                    
                    # Track file types
                    ext = file_info['extension']
                    stats['file_types'][ext] = stats['file_types'].get(ext, 0) + 1
                    
                    # Track largest file
                    if file_info['size_bytes'] > stats['largest_file_size']:
                        stats['largest_file'] = str(file_path)
                        stats['largest_file_size'] = file_info['size_bytes']
                
                except Exception as e:
                    stats['errors'].append(f"{file_path}: {str(e)}")
        
        except Exception as e:
            stats['errors'].append(f"Directory walk error: {str(e)}")
        
        # Add derived stats
        stats['total_size_mb'] = round(stats['total_size_bytes'] / (1024 * 1024), 2)
        stats['average_file_size_kb'] = (
            round(stats['total_size_bytes'] / (1024 * stats['total_files']), 2) 
            if stats['total_files'] > 0 else 0
        )
        
        return stats