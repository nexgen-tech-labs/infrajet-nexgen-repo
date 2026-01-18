#!/usr/bin/env python3
"""
Configuration Validation Script.

This script provides a command-line interface for validating application configuration.
It can be used during deployment or development to ensure all configurations are correct.
"""

import sys
import json
from typing import Dict, Any

from ..settings import get_settings
from . import (
    check_configuration_health,
    quick_health_check,
    validate_startup_configuration,
    validate_supabase_configuration,
    quick_validate_supabase_config,
)


def print_health_report(health_report: Dict[str, Any], verbose: bool = False) -> None:
    """Print a formatted health report."""
    
    overall_status = health_report["overall_status"]
    summary = health_report["summary"]
    
    print(f"\n🔍 Configuration Health Check Report")
    print(f"{'='*50}")
    print(f"Overall Status: {overall_status.upper()}")
    print(f"Timestamp: {health_report.get('timestamp', 'N/A')}")
    
    print(f"\n📊 Summary:")
    print(f"  ✅ Healthy: {summary['healthy']}")
    print(f"  ⚠️  Warnings: {summary['warnings']}")
    print(f"  ❌ Unhealthy: {summary['unhealthy']}")
    print(f"  ⏸️  Disabled: {summary['disabled']}")
    
    print(f"\n🔧 Components:")
    for name, component in health_report["components"].items():
        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️",
            "unhealthy": "❌",
            "disabled": "⏸️"
        }.get(component.status, "❓")
        
        print(f"  {status_emoji} {name.title()}: {component.message}")
        
        if verbose and component.errors:
            for error in component.errors:
                print(f"    ❌ {error}")
        
        if verbose and component.warnings:
            for warning in component.warnings:
                print(f"    ⚠️  {warning}")
    
    if health_report.get("recommendations"):
        print(f"\n💡 Recommendations:")
        for rec in health_report["recommendations"]:
            print(f"  • {rec}")


def validate_configuration(verbose: bool = False, json_output: bool = False) -> bool:
    """
    Validate application configuration.
    
    Args:
        verbose: Show detailed information
        json_output: Output results as JSON
        
    Returns:
        True if configuration is valid, False otherwise
    """
    
    try:
        if json_output:
            # JSON output mode
            health_report = check_configuration_health()
            print(json.dumps(health_report, indent=2, default=str))
            return health_report["overall_status"] in ["healthy", "warning"]
        
        else:
            # Human-readable output mode
            print("🚀 Validating Application Configuration...")
            
            # Quick health check first
            is_healthy, message = quick_health_check()
            print(f"Quick Check: {message}")
            
            if verbose:
                # Detailed health check
                health_report = check_configuration_health()
                print_health_report(health_report, verbose=True)
                
                # Additional detailed checks
                print(f"\n🔐 Authentication Configuration:")
                settings = get_settings()
                
                if settings.SUPABASE_AUTH_ENABLED:
                    supabase_valid, supabase_msg = quick_validate_supabase_config(settings)
                    status_emoji = "✅" if supabase_valid else "❌"
                    print(f"  {status_emoji} Supabase: {supabase_msg}")
                
                print(f"\n🚦 Feature Flags:")
                feature_flags = settings.get_feature_flags()
                for flag, enabled in feature_flags.items():
                    status_emoji = "✅" if enabled else "⏸️"
                    print(f"  {status_emoji} {flag}: {enabled}")
                
                # Startup validation
                print(f"\n🚀 Startup Validation:")
                startup_valid, startup_errors = validate_startup_configuration()
                if startup_valid:
                    print("  ✅ All critical configurations are valid for startup")
                else:
                    print("  ❌ Critical configuration errors detected:")
                    for error in startup_errors:
                        print(f"    • {error}")
            
            return is_healthy
    
    except Exception as e:
        if json_output:
            error_report = {
                "overall_status": "unhealthy",
                "error": str(e),
                "timestamp": None
            }
            print(json.dumps(error_report, indent=2))
        else:
            print(f"❌ Configuration validation failed: {str(e)}")
        
        return False


def main():
    """Main entry point for the configuration validation script."""
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate application configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m app.core.config.validate_config                    # Quick validation
  python -m app.core.config.validate_config --verbose          # Detailed validation
  python -m app.core.config.validate_config --json             # JSON output
  python -m app.core.config.validate_config --verbose --json   # Detailed JSON output
        """
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed validation information"
    )
    
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    # Validate configuration
    is_valid = validate_configuration(verbose=args.verbose, json_output=args.json)
    
    # Exit with appropriate code
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()