#!/usr/bin/env python3
"""
Planning-Only Runner for RAQ.AI Document Generation Service

This script runs only the Content Planning Team workflow with configurable parameters.
Uses sequential job IDs stored in jobid.txt for tracking.
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

# Content description/requirements
USER_INPUT = "Create a RAQ project planning document using the assets provided."

# Template URL for structure analysis (optional)
TEMPLATE_URL = None  # Set to None if not needed

# Available options: payment_comparisons, payment_termonology
CONTENT_BRIEF_TYPE = "raq_project_planning"

# Output directory for job folders
OUTPUT_BASE_PATH = Path(__file__).parent / "output"

# ==========================================
# MAIN EXECUTION
# ==========================================

async def main():
    """Main execution function for planning-only workflow."""
    print("🚀 RAQ.AI Planning-Only Runner")
    print("=" * 50)
    
    # Get next job ID
    base_path = Path(__file__).parent
    job_id = get_next_job_id(base_path)
    print(f"📋 Job ID: {job_id}")
    
    # Display configuration
    print(f"📝 User Input: {USER_INPUT}")
    print(f"🔗 Template URL: {TEMPLATE_URL}")
    print(f"📄 Content Brief Type: {CONTENT_BRIEF_TYPE}")
    print(f"📁 Output Path: {OUTPUT_BASE_PATH}")
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
    
    # Run planning-only workflow
    try:
        print(f"🎯 Starting Planning Team workflow for job {job_id}...")
        print()
        
        success = await runner.run_planning_only(
            job_id=job_id,
            user_input=USER_INPUT,
            template_url=TEMPLATE_URL,
            content_brief_type=CONTENT_BRIEF_TYPE,
            output_base_path=OUTPUT_BASE_PATH,
            custom_content_brief=None  # Not used in this runner
        )
        
        if success:
            print()
            print("🎉 Planning workflow completed successfully!")
            print(f"📁 Job folder: {OUTPUT_BASE_PATH / job_id}")
            print(f"📄 Planning output: {OUTPUT_BASE_PATH / job_id / 'planning_output.md'}")
            print(f"📊 Configuration: {OUTPUT_BASE_PATH / job_id / 'pipeline_config.json'}")
            print()
            print("🔍 Next steps:")
            print("  - Review the planning output")
            print("  - Run production workflow if needed")
            print("  - Adjust configuration constants for next run")
            return 0
        else:
            print("❌ Planning workflow failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error during planning workflow: {e}")
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
    print(f"   Output Directory: {job_history['output_directory']}")
    print(f"   Total Jobs: {job_history['total_jobs']}")
    
    if job_history['latest_job']:
        print(f"   Latest Job: {job_history['latest_job']}")
    
    if job_history['job_folders']:
        print(f"   Job History: {', '.join(job_history['job_folders'])}")

if __name__ == "__main__":
    # Print status before running
    print_status()
    print()
    
    # Run the main workflow
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
