#!/usr/bin/env python3
"""
Full Pipeline Runner for RAQ.AI Document Generation Service

This script runs the complete workflow: Content Planning Team → Content Production Team → Process Analysis.
Uses sequential job IDs stored in jobid.txt for tracking.

QUICK SETUP: Edit the GLOBAL CONFIGURATION VARIABLES section below to set rerun/start-from behavior.

Usage:
  python run-pipeline.py                                    # Run full workflow with new job ID
  python run-pipeline.py --rerun 0060                       # Rerun full workflow using existing job 0060
  python run-pipeline.py --rerun 0060 --start-from Content_Analysis_Team  # Rerun from specific team
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src/doc-gen to Python path for imports
sys.path.insert(0, str(Path(__file__).parent / "src" / "doc-gen"))

# ========================================
# GLOBAL CONFIGURATION VARIABLES
# ========================================
# Set these variables to control pipeline behavior without command-line args
# These take priority over command-line arguments when set

DOCUMENT_TYPE = "RAQ"

# RERUN CONFIGURATION
# Set to a job ID (e.g., "0060") to rerun from existing job, or None for new job
RERUN_JOB_ID = None # Example: "0061"

# START FROM TEAM CONFIGURATION  
# Set to team name to start from specific team, or None to start from beginning
# Quick Configuration Examples:

LAST_TEAM_EXECUTED = None

# ========================================

from pipeline_runner import PipelineRunner
from job_utils import (
    get_next_job_id_for_document_type, 
    peek_current_job_id_for_document_type, 
    get_job_history_for_document_type,
    get_next_job_id, 
    peek_current_job_id, 
    get_job_history  # Legacy functions for backward compatibility
)

# ==========================================
# COMMAND LINE ARGUMENT PARSING
# ==========================================

def parse_arguments():
    """Parse command line arguments for pipeline execution."""
    parser = argparse.ArgumentParser(
        description="RAQ.AI Pipeline Runner - Execute document generation workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run-pipeline.py                                    # Run full workflow with new job ID
  python run-pipeline.py --rerun 0060                       # Rerun full workflow using existing job 0060
  python run-pipeline.py --last-team-executed Epic_Discovery_Team --source-job-id 0060  # Run dependent teams
        """
    )
    
    parser.add_argument(
        '--rerun',
        type=str,
        help='Rerun using existing job ID (e.g., 0060)'
    )
    
    parser.add_argument(
        '--last-team-executed',
        type=str,
        help='Run all teams that depend on this team (e.g., Epic_Discovery_Team)'
    )
    
    parser.add_argument(
        '--source-job-id',
        type=str,
        help='Source job ID to copy assets from (used with --last-team-executed)'
    )
    
    return parser.parse_args()

# ==========================================
# CONFIGURATION CONSTANTS - EDIT AS NEEDED
# ==========================================

# Content description/requirements
USER_INPUT = "Create a RAQ project planning document using the assets provided."

# Template URL for structure analysis (optional)
TEMPLATE_URL = None  # Set to None if not needed

# Available document types: RAQ (others can be added later)


# Output directory for job folders
OUTPUT_BASE_PATH = Path(__file__).parent / "output"

# Assets directory for document assets (PDFs, docs, etc.)
ASSETS_BASE_PATH = Path(__file__).parent / "assets"

# ==========================================
# MAIN EXECUTION
# ==========================================

async def main():
    """Main execution function for full pipeline workflow."""
    # Parse command line arguments
    args = parse_arguments()
    
    print("🚀 RAQ.AI Full Pipeline Runner")
    print("=" * 50)
    
    # Use global variables if set, otherwise use command-line arguments
    rerun_job = RERUN_JOB_ID if RERUN_JOB_ID is not None else args.rerun
    last_team_executed = LAST_TEAM_EXECUTED if LAST_TEAM_EXECUTED is not None else args.last_team_executed
    source_job_id = args.source_job_id
    
    # Show configuration
    if RERUN_JOB_ID or LAST_TEAM_EXECUTED:
        print("🔧 Using Global Configuration:")
        if RERUN_JOB_ID:
            print(f"   RERUN_JOB_ID = {RERUN_JOB_ID}")
        if LAST_TEAM_EXECUTED:
            print(f"   LAST_TEAM_EXECUTED = {LAST_TEAM_EXECUTED}")
        print()
    
    # Determine job ID based on configuration and document type
    base_path = Path(__file__).parent
    
    # Handle source_job_id parameter (can be from --source-job-id or derived from --rerun)
    if not source_job_id and rerun_job:
        source_job_id = rerun_job
    
    if rerun_job:
        # Get new job ID but use existing job as source
        if not source_job_id:
            source_job_id = rerun_job
        job_id = get_next_job_id_for_document_type(DOCUMENT_TYPE, OUTPUT_BASE_PATH)
        print(f"📋 New Job ID: {job_id} (based on job {source_job_id})")
        
        # Verify source job folder exists (check both new and legacy locations)
        source_job_folder = OUTPUT_BASE_PATH / DOCUMENT_TYPE / source_job_id
        if not source_job_folder.exists():
            # Check legacy location for backward compatibility
            legacy_source_folder = OUTPUT_BASE_PATH / source_job_id
            if legacy_source_folder.exists():
                source_job_folder = legacy_source_folder
                print(f"📁 Using legacy job location: {source_job_folder}")
            else:
                print(f"❌ Error: Source job folder not found in {OUTPUT_BASE_PATH / DOCUMENT_TYPE / source_job_id} or {legacy_source_folder}")
                return 1
    elif source_job_id:
        # Using source_job_id without rerun (for partial execution)
        job_id = get_next_job_id_for_document_type(DOCUMENT_TYPE, OUTPUT_BASE_PATH)
        print(f"📋 New Job ID: {job_id} (using source job {source_job_id})")
        
        # Verify source job folder exists
        source_job_folder = OUTPUT_BASE_PATH / DOCUMENT_TYPE / source_job_id
        if not source_job_folder.exists():
            legacy_source_folder = OUTPUT_BASE_PATH / source_job_id
            if legacy_source_folder.exists():
                source_job_folder = legacy_source_folder
                print(f"📁 Using legacy job location: {source_job_folder}")
            else:
                print(f"❌ Error: Source job folder not found in {OUTPUT_BASE_PATH / DOCUMENT_TYPE / source_job_id} or {legacy_source_folder}")
                return 1
    else:
        job_id = get_next_job_id_for_document_type(DOCUMENT_TYPE, OUTPUT_BASE_PATH)
        print(f"📋 New Job ID: {job_id}")
    
    # Create the document-type-specific job folder path
    job_folder_path = OUTPUT_BASE_PATH / DOCUMENT_TYPE / job_id
    
    # Show execution mode configuration
    if last_team_executed:
        print(f"🔄 Running teams that depend on: {last_team_executed}")
        if not source_job_id:
            print("⚠️  Warning: last-team-executed requires source job data")
    
    # Display configuration
    print(f"📝 User Input: {USER_INPUT}")
    print(f"🔗 Template URL: {TEMPLATE_URL}")
    print(f"📄 Document Type: {DOCUMENT_TYPE}")
    print(f"📁 Output Path: {OUTPUT_BASE_PATH}")
    print(f"📁 Assets Path: {ASSETS_BASE_PATH}")
    
    # Collect assets from assets directory
    assets = []
    if ASSETS_BASE_PATH.exists() and ASSETS_BASE_PATH.is_dir():
        for asset_file in ASSETS_BASE_PATH.glob("*"):
            if asset_file.is_file() and not asset_file.name.startswith('.'):
                assets.append(str(asset_file))
        print(f"📎 Found {len(assets)} asset(s): {[Path(a).name for a in assets]}")
    else:
        print("📎 No assets directory found or no assets available")
    
    print()
    print("🔄 Pipeline Steps:")
    print("   1. Content Planning Team")
    print("   2. Content Production Team") 
    print("   3. Process Analysis")
    print()
    
    # Ensure output directory exists
    OUTPUT_BASE_PATH.mkdir(parents=True, exist_ok=True)
    
    # Initialize pipeline runner
    try:
        print("🔧 Initializing Pipeline Runner...")
        runner = PipelineRunner()
        print("✅ Pipeline Runner initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Pipeline Runner: {e}")
        return 1
    
    # Run complete pipeline workflow
    try:
        print(f"🎯 Starting Full Pipeline workflow for job {job_id}...")
        print()
        
        success = await runner.run_pipeline(
            job_id=job_id,
            user_input=USER_INPUT,
            template_url=TEMPLATE_URL,
            document_type=DOCUMENT_TYPE,
            output_base_path=OUTPUT_BASE_PATH / DOCUMENT_TYPE,  # Document-type-specific path
            assets=assets if assets else None,
            last_team_executed=last_team_executed,
            source_job_id=source_job_id  # New parameter for rerun source
        )
        
        if success:
            print()
            print(f"🎉 Full pipeline completed successfully!")
            print(f"📁 Job folder: {job_folder_path}")
            print(f"📄 Planning output: {job_folder_path / 'planning_output.md'}")
            print(f"📄 Production output: {job_folder_path / 'production_output.md'}")
            print(f"📄 Process analysis: {job_folder_path / 'process_analysis.md'}")
            print(f"📊 Configuration: {job_folder_path / 'pipeline_config.json'}")
            print()
            print("🔍 Generated Files:")
            if job_folder_path.exists():
                for file in sorted(job_folder_path.glob("*.md")):
                    print(f"   - {file.name}")
            print()
            print("🔍 Next steps:")
            print("  - Review all generated outputs")
            print("  - Check process analysis for insights")
            print("  - Adjust configuration constants for next run")
            return 0
        else:
            print("❌ Full pipeline workflow failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error during pipeline workflow: {e}")
        import traceback
        traceback.print_exc()
        return 1

def print_status():
    """Print current status information for all document types."""
    base_path = Path(__file__).parent
    
    print("📊 Current Status:")
    
    # Show document-type-specific status
    current_job_id = peek_current_job_id_for_document_type(DOCUMENT_TYPE, OUTPUT_BASE_PATH)
    next_job_id = f"{int(current_job_id) + 1:04d}" if current_job_id != "0000" else "0001"
    job_history = get_job_history_for_document_type(DOCUMENT_TYPE, OUTPUT_BASE_PATH)
    
    print(f"   Document Type: {DOCUMENT_TYPE}")
    print(f"   Current Job ID: {current_job_id}")
    print(f"   Next Job ID: {next_job_id}")
    print(f"   Output Directory: {OUTPUT_BASE_PATH / DOCUMENT_TYPE}")
    print(f"   Total Jobs: {len(job_history)}")
    
    if job_history:
        print(f"   Latest Job: {job_history[0]}")
        print(f"   Job History: {', '.join(job_history)}")
    else:
        print(f"   No jobs yet for document type: {DOCUMENT_TYPE}")
    
    # Show legacy status for backward compatibility
    legacy_job_history = get_job_history(OUTPUT_BASE_PATH, base_path)
    if legacy_job_history['job_folders']:
        print(f"   Legacy Jobs (flat structure): {', '.join(legacy_job_history['job_folders'])}")

if __name__ == "__main__":
    # Print status before running
    print_status()
    print()
    
    # Run the main workflow
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
