#!/usr/bin/env python3
"""
Modern Pipeline Runner

Uses the new WorkflowManager architecture that:
- Auto-derives workflow paths from document types
- Handles asset management automatically
- Provides self-contained job execution
"""

import sys
import argparse
from pathlib import Path

# Add the src/doc-gen directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src" / "doc-gen"))

from workflow import WorkflowManager
from workflow_orchestrator import WorkflowOrchestrator
from team_runner import TeamRunnerFactory
from logger import ConsoleLoggerFactory
from job_utils import get_next_job_id_for_document_type


def run_pipeline(document_type: str, assets: list = None, output_base: str = "./output"):
    """Run the modern pipeline with the new architecture."""
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
    parser = argparse.ArgumentParser(description="Modern RAQ Pipeline Runner")
    parser.add_argument("--document-type", required=True, 
                       help="Document type (e.g., RAQ, simple)")
    parser.add_argument("--assets", nargs="*", 
                       help="Asset files to process")
    parser.add_argument("--output", default="./output",
                       help="Output directory (default: ./output)")
    
    args = parser.parse_args()
    
    # Validate assets exist
    validated_assets = []
    if args.assets:
        for asset in args.assets:
            asset_path = Path(asset)
            if asset_path.exists():
                validated_assets.append(str(asset_path.resolve()))
            else:
                print(f"❌ Asset not found: {asset}")
                sys.exit(1)
    
    run_pipeline(
        document_type=args.document_type,
        assets=validated_assets,
        output_base=args.output
    )


if __name__ == "__main__":
    main()
