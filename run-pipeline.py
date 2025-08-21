#!/usr/bin/env python3
"""
RAQ Pipeline Runner

Main entry point for document generation pipeline that:
- Auto-derives workflow paths from document types
- Handles asset management automatically
- Provides self-contained job execution
"""

import sys
import argparse
from pathlib import Path

# Configuration variables for easy VS Code execution
# Change these values and run the script directly from VS Code
DOCUMENT_TYPE = "RAQ"  # Options: "RAQ", "simple", "test"
ASSETS_PATH = "assets"    # Path to assets folder or file
OUTPUT_BASE = "./output"  # Output directory

# Add the src/doc-gen directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src" / "doc-gen"))

from workflow import WorkflowManager
from workflow_orchestrator import WorkflowOrchestrator
from team_runner import TeamRunnerFactory
from logger import ConsoleLoggerFactory


def get_next_job_id_for_document_type(document_type: str, output_base_path: Path = None) -> str:
    """
    Get the next sequential job ID for a specific document type.
    Creates document-type-specific directory and jobid.txt file if they don't exist.

    Args:
        document_type: Document type (e.g., 'RAQ', 'test', etc.)
        output_base_path: Base output directory. Defaults to 'output' in current directory.

    Returns:
        str: Next job ID as a 4-digit string (e.g., "0003")
    """
    if output_base_path is None:
        output_base_path = Path.cwd() / "output"
    
    # Create document-type-specific directory
    doc_type_dir = output_base_path / document_type
    doc_type_dir.mkdir(parents=True, exist_ok=True)
    
    jobid_file = doc_type_dir / "jobid.txt"
    
    if not jobid_file.exists():
        # Create initial job ID file
        current_id = 1
        with open(jobid_file, 'w') as f:
            f.write("0001")
    else:
        # Read current job ID and increment
        with open(jobid_file, 'r') as f:
            current_id_str = f.read().strip()
            current_id = int(current_id_str) + 1
    
    # Format as 4-digit string and update file
    new_job_id = f"{current_id:04d}"
    with open(jobid_file, 'w') as f:
        f.write(new_job_id)
    
    return new_job_id


def run_pipeline(document_type: str, assets: list = None, output_base: str = "./output"):
    """Run the pipeline with the new architecture."""
    print(f"🚀 Starting {document_type} Pipeline")
    print("=" * 50)
    
    # Setup
    logger_factory = ConsoleLoggerFactory()
    job_id = get_next_job_id_for_document_type(document_type)
    
    print(f"📋 Document Type: {document_type}")
    print(f"🆔 Job ID: {job_id}")
    print(f"📂 Output Base: {output_base}")
    if assets:
        print(f"📄 Assets: {len(assets)} files")
        for asset in assets:
            print(f"   📄 {Path(asset).name}")
    
    # Initialize WorkflowManager (no workflow path needed - derived from document type)
    wm = WorkflowManager(logger_factory)
    orchestrator = WorkflowOrchestrator(logger_factory=logger_factory)
    team_runner_factory = TeamRunnerFactory(logger_factory)
    
    try:
        print(f"\n🔧 Initializing workflow...")
        wm.initialize(
            job_id=job_id,
            document_type=document_type,
            output_base_path=output_base,
            orchestrator=orchestrator,
            team_runner_factory=team_runner_factory,
            assets=assets or []
        )
        
        print(f"✅ Workflow initialized successfully")
        print(f"   📊 Teams: {len(wm.teams)}")
        print(f"   📂 Job folder: {wm.job_folder}")
        
        # Show team structure
        print(f"\n🔧 Team Structure:")
        for i, team in enumerate(wm.teams, 1):
            print(f"   {i}. {team.id}")
            print(f"      📄 Output: {team.output_file}")
            print(f"      📋 Template: {team.template}")
            if team.depends_on:
                print(f"      🔗 Depends on: {team.depends_on}")
        
        # Show asset summary
        if wm.asset_manager:
            summary = wm.asset_manager.get_asset_summary()
            print(f"\n📦 Asset Summary:")
            print(f"   Total files: {summary['total_files']}")
            print(f"   File types: {summary['types']}")
            
            asset_info = wm.asset_manager.format_assets_for_agent()
            if asset_info.strip():
                print(f"   🧠 Vector memory: Created")
            else:
                print(f"   🧠 Vector memory: Not created")
        
        # Execute workflow
        print(f"\n🎯 Executing workflow...")
        print(f"   This may take several minutes...")
        
        result = wm.run()
        
        if result:
            print(f"\n✅ Pipeline completed successfully!")
            
            # Show final statuses
            print(f"\n📈 Final Results:")
            for team in wm.teams:
                status = orchestrator.get(team.id)
                output_file = wm.job_folder / f"{team.output_file}.md"
                
                if output_file.exists():
                    size = output_file.stat().st_size
                    print(f"   ✅ {team.id}: {status} ({size} bytes)")
                else:
                    print(f"   ⚠️ {team.id}: {status} (no output file)")
            
            print(f"\n📂 Results saved to: {wm.job_folder}")
            
        else:
            print(f"\n⚠️ Pipeline completed with errors")
            print(f"📂 Check logs in: {wm.job_folder}")
            
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run document generation pipeline')
    parser.add_argument('document_type', nargs='?', default=DOCUMENT_TYPE, 
                       help=f'Type of document to generate (RAQ, simple, test) - Default: {DOCUMENT_TYPE}')
    parser.add_argument('--assets', default=ASSETS_PATH, 
                       help=f'Assets folder to include - Default: {ASSETS_PATH}')
    
    args = parser.parse_args()
    
    # Use configuration variables if running without arguments
    document_type = args.document_type
    assets_path = args.assets
    
    print(f"🔧 Configuration:")
    print(f"   📋 Document Type: {document_type}")
    print(f"   📁 Assets Path: {assets_path}")
    print(f"   📂 Output Base: {OUTPUT_BASE}")
    print()
    
    # Handle assets - can be a folder or individual files
    validated_assets = []
    assets_path_obj = Path(assets_path)
    
    if assets_path_obj.exists():
        if assets_path_obj.is_dir():
            # If it's a directory, add all files in it
            for file_path in assets_path_obj.rglob('*'):
                if file_path.is_file():
                    validated_assets.append(str(file_path.resolve()))
        else:
            # If it's a file, add it directly
            validated_assets.append(str(assets_path_obj.resolve()))
    else:
        print(f"❌ Assets path not found: {assets_path}")
        sys.exit(1)
    
    run_pipeline(
        document_type=document_type,
        assets=validated_assets,
        output_base=OUTPUT_BASE
    )


if __name__ == "__main__":
    main()
