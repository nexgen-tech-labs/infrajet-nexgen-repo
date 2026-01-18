"""Terraform parsing API routes."""

from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from app.services.tree_sitter_service import TreeSitterService


router = APIRouter(prefix="/terraform", tags=["terraform"])


class ParseFileRequest(BaseModel):
    file_path: str


class ParseDirectoryRequest(BaseModel):
    directory_path: str
    recursive: bool = True
    max_files: int = 100


class SearchResourcesRequest(BaseModel):
    directory_path: str
    resource_type: str


@router.post("/parse/file")
async def parse_terraform_file(request: ParseFileRequest) -> Dict[str, Any]:
    """Parse a single Terraform file."""
    service = TreeSitterService()
    return await service.parse_terraform_file(request.file_path)


@router.post("/parse/directory")
async def parse_terraform_directory(request: ParseDirectoryRequest) -> Dict[str, Any]:
    """Parse all Terraform files in a directory."""
    service = TreeSitterService()
    return await service.parse_terraform_directory(
        request.directory_path,
        request.recursive,
        request.max_files
    )


@router.post("/resources")
async def get_terraform_resources(request: ParseFileRequest) -> List[Dict[str, Any]]:
    """Get all Terraform resources from a file."""
    service = TreeSitterService()
    return await service.get_terraform_resources(request.file_path)


@router.post("/modules")
async def get_terraform_modules(request: ParseFileRequest) -> List[Dict[str, Any]]:
    """Get all Terraform modules from a file."""
    service = TreeSitterService()
    return await service.get_terraform_modules(request.file_path)


@router.post("/variables")
async def get_terraform_variables(request: ParseFileRequest) -> List[Dict[str, Any]]:
    """Get all Terraform variables from a file."""
    service = TreeSitterService()
    return await service.get_terraform_variables(request.file_path)


@router.post("/outputs")
async def get_terraform_outputs(request: ParseFileRequest) -> List[Dict[str, Any]]:
    """Get all Terraform outputs from a file."""
    service = TreeSitterService()
    return await service.get_terraform_outputs(request.file_path)


@router.post("/search/resources")
async def search_resources_by_type(request: SearchResourcesRequest) -> List[Dict[str, Any]]:
    """Search for Terraform resources of a specific type."""
    service = TreeSitterService()
    return await service.search_resources_by_type(
        request.directory_path,
        request.resource_type
    )


@router.post("/analyze")
async def analyze_terraform_project(request: ParseDirectoryRequest) -> Dict[str, Any]:
    """Analyze an entire Terraform project."""
    service = TreeSitterService()
    return await service.analyze_terraform_project(request.directory_path)


@router.post("/validate")
async def validate_terraform_syntax(request: ParseFileRequest) -> Dict[str, Any]:
    """Validate Terraform file syntax."""
    service = TreeSitterService()
    return await service.validate_terraform_syntax(request.file_path)


@router.get("/supported-types")
async def get_supported_file_types() -> List[str]:
    """Get list of supported file extensions."""
    service = TreeSitterService()
    return service.get_supported_file_types()


# Example usage endpoints for testing
@router.get("/example/aws-resources")
async def find_aws_resources(
    directory_path: str = Query(..., description="Path to Terraform directory")
) -> Dict[str, Any]:
    """Find all AWS resources in a Terraform project."""
    service = TreeSitterService()
    
    # Common AWS resource types
    aws_resource_types = [
        "aws_instance",
        "aws_s3_bucket",
        "aws_vpc",
        "aws_subnet",
        "aws_security_group",
        "aws_iam_role",
        "aws_lambda_function",
        "aws_rds_instance",
        "aws_ecs_cluster",
        "aws_eks_cluster"
    ]
    
    all_aws_resources = {}
    
    for resource_type in aws_resource_types:
        try:
            resources = await service.search_resources_by_type(directory_path, resource_type)
            if resources:
                all_aws_resources[resource_type] = resources
        except Exception as e:
            # Continue with other resource types if one fails
            continue
    
    return {
        "directory_path": directory_path,
        "aws_resources": all_aws_resources,
        "total_aws_resources": sum(len(resources) for resources in all_aws_resources.values())
    }


@router.get("/example/project-stats")
async def get_project_statistics(
    directory_path: str = Query(..., description="Path to Terraform directory")
) -> Dict[str, Any]:
    """Get comprehensive statistics about a Terraform project."""
    service = TreeSitterService()
    
    try:
        analysis = await service.analyze_terraform_project(directory_path)
        
        # Additional insights
        insights = {
            "complexity_score": _calculate_complexity_score(analysis),
            "recommendations": _generate_recommendations(analysis),
            "file_distribution": _analyze_file_distribution(analysis)
        }
        
        return {
            **analysis,
            "insights": insights
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _calculate_complexity_score(analysis: Dict[str, Any]) -> int:
    """Calculate a simple complexity score for the project."""
    summary = analysis.get("summary", {})
    
    score = 0
    score += summary.get("total_resources", 0) * 2
    score += summary.get("total_modules", 0) * 5
    score += summary.get("total_files", 0) * 1
    
    return min(score, 100)  # Cap at 100


def _generate_recommendations(analysis: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on project analysis."""
    recommendations = []
    summary = analysis.get("summary", {})
    
    if summary.get("total_modules", 0) == 0:
        recommendations.append("Consider using modules to organize your Terraform code")
    
    if summary.get("total_variables", 0) == 0:
        recommendations.append("Add variables to make your configuration more flexible")
    
    if summary.get("total_outputs", 0) == 0:
        recommendations.append("Add outputs to expose important resource information")
    
    if summary.get("failed_parses", 0) > 0:
        recommendations.append("Fix syntax errors in failed files")
    
    return recommendations


def _analyze_file_distribution(analysis: Dict[str, Any]) -> Dict[str, int]:
    """Analyze the distribution of different file types."""
    distribution = {}
    
    for file_info in analysis.get("files", []):
        file_type = file_info.get("file_type", "unknown")
        distribution[file_type] = distribution.get(file_type, 0) + 1
    
    return distribution