#!/usr/bin/env python3
"""
Production-Only Runner for RAQ.AI Document Generation Service

This script runs only the Content Production Team workflow using an existing job's planning output.
Specify the target job ID to rerun production for that specific planning result.
"""

import asyncio
import sys
from pathlib import Path

# Add src/doc-gen to Python path for imports
sys.path.insert(0, str(Path(__file__).parent / "src" / "doc-gen"))

from pipeline_runner import PipelineRunner
from job_utils import get_next_job_id, peek_current_job_id, get_job_history

# ==========================================
# CONFIGURATION CONSTANTS - EDIT AS NEEDED
# ==========================================

# Target job ID to rerun production for (e.g., 5 for job 0005)
# This will use the planning_output.md from that job's folder
TARGET_JOB_ID = 2  # Will use output/0002/planning_output.md

# Output directory for job folders
OUTPUT_BASE_PATH = Path(__file__).parent / "output"

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def format_job_id(job_number: int) -> str:
    """Format job number as 4-digit string (e.g., 5 -> '0005')"""
    return f"{job_number:04d}"

def find_planning_output(target_job_id: int, output_path: Path) -> Path:
    """
    Find the planning output file for the specified job ID.
    
    Args:
        target_job_id: The job number to find (e.g., 5 for job 0005)
        output_path: Base output directory
        
    Returns:
        Path: Path to the planning_output.md file
        
    Raises:
        FileNotFoundError: If the job folder or planning file doesn't exist
    """
    job_id_str = format_job_id(target_job_id)
    job_folder = output_path / job_id_str
    planning_file = job_folder / "planning_output.md"
    
    if not job_folder.exists():
        raise FileNotFoundError(f"Job folder not found: {job_folder}")
    
    if not planning_file.exists():
        raise FileNotFoundError(f"Planning output not found: {planning_file}")
    
    return planning_file

def list_available_jobs(output_path: Path) -> list:
    """List all available job folders for production rerun."""
    if not output_path.exists():
        return []
    
    job_folders = []
    for folder in output_path.iterdir():
        if folder.is_dir() and folder.name.isdigit() and len(folder.name) == 4:
            planning_file = folder / "planning_output.md"
            if planning_file.exists():
                job_folders.append({
                    "job_id": folder.name,
                    "job_number": int(folder.name),
                    "planning_file": planning_file,
                    "has_production": (folder / "production_output.md").exists()
                })
    
    return sorted(job_folders, key=lambda x: x["job_number"])

# ==========================================
# MAIN EXECUTION
# ==========================================

async def main():
    """Main execution function for production-only workflow."""
    print("🚀 RAQ.AI Production-Only Runner")
    print("=" * 50)
    
    # List available jobs
    available_jobs = list_available_jobs(OUTPUT_BASE_PATH)
    
    if not available_jobs:
        print("❌ No jobs with planning output found!")
        print(f"   Output directory: {OUTPUT_BASE_PATH}")
        print("   Run the planning workflow first to create jobs.")
        return 1
    
    print("📋 Available Jobs:")
    for job in available_jobs:
        status = "✅ Has production" if job["has_production"] else "📝 Planning only"
        print(f"   Job {job['job_number']:02d} ({job['job_id']}) - {status}")
    print()
    
    # Validate target job ID
    target_job_str = format_job_id(TARGET_JOB_ID)
    print(f"🎯 Target Job: {TARGET_JOB_ID} ({target_job_str})")
    
    try:
        planning_file = find_planning_output(TARGET_JOB_ID, OUTPUT_BASE_PATH)
        print(f"📄 Planning Input: {planning_file}")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print()
        print("💡 Available jobs with planning output:")
        for job in available_jobs:
            print(f"   - Job {job['job_number']} ({job['job_id']})")
        return 1
    
    # Get next job ID for the production run
    base_path = Path(__file__).parent
    new_job_id = get_next_job_id(base_path)
    print(f"📋 New Production Job ID: {new_job_id}")
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
    
    # Run production-only workflow
    try:
        print(f"🎯 Starting Production Team workflow...")
        print(f"   Source: Job {TARGET_JOB_ID} planning output")
        print(f"   Target: Job {new_job_id}")
        print()
        
        success = runner.run_production_only(
            job_id=new_job_id,
            planning_file_path=str(planning_file)
        )
        
        if success:
            print()
            print("🎉 Production workflow completed successfully!")
            print(f"📁 Job folder: {OUTPUT_BASE_PATH / new_job_id}")
            print(f"📄 Source planning: {planning_file}")
            print(f"📄 New production output: {OUTPUT_BASE_PATH / new_job_id / 'production_output.md'}")
            print()
            print("🔍 Next steps:")
            print("  - Review the new production output")
            print("  - Compare with previous production runs")
            print("  - Adjust TARGET_JOB_ID for different source")
            return 0
        else:
            print("❌ Production workflow failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error during production workflow: {e}")
        import traceback
        traceback.print_exc()
        return 1

def print_status():
    """Print current status information."""
    base_path = Path(__file__).parent
    job_history = get_job_history(OUTPUT_BASE_PATH, base_path)
    
    print("📊 Current Status:")
    print(f"   Current Job ID: {job_history['current_job_id']}")
    print(f"   Next Job ID: {job_history['next_job_id']}")
    print(f"   Target Job ID: {TARGET_JOB_ID} ({format_job_id(TARGET_JOB_ID)})")
    print(f"   Output Directory: {job_history['output_directory']}")
    print(f"   Total Jobs: {job_history['total_jobs']}")
    
    if job_history['latest_job']:
        print(f"   Latest Job: {job_history['latest_job']}")
    
    # Show available jobs for production rerun
    available_jobs = list_available_jobs(OUTPUT_BASE_PATH)
    if available_jobs:
        job_list = [f"{job['job_number']}" for job in available_jobs]
        print(f"   Available for Production: {', '.join(job_list)}")

if __name__ == "__main__":
    # Print status before running
    print_status()
    print()
    
    # Run the main workflow
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
