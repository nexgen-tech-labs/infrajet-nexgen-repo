"""
Services package for InfraJet application.
"""

try:
    from .azure_file_service import AzureFileService, get_azure_file_service
    _azure_available = True
except ImportError:
    _azure_available = False
    AzureFileService = None
    get_azure_file_service = None

__all__ = []
if _azure_available:
    __all__.extend([
        "AzureFileService",
        "get_azure_file_service"
    ])