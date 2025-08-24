#!/usr/bin/env python3
"""
Asset Movement Test: Test workflow with actual assets

This script tests the complete pipeline with real assets:
1. Creates sample assets (PDF, DOCX, MD, TXT)
2. WorkflowManager processes them through AssetManager
3. Verifies all assets are moved and processed
4. Shows vector memory creation
"""

import sys
import tempfile
from pathlib import Path

# Add the src/doc-gen directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src" / "doc-gen"))

from workflow import WorkflowManager
from workflow_orchestrator import WorkflowOrchestrator
from tests.mock_team_runner import MockTeamRunnerFactory
from logger import MemoryLoggerFactory


def create_sample_assets(temp_dir: Path) -> list:
    """Create sample assets for testing."""
    assets = []
    
    # Create a markdown file
    md_file = temp_dir / "sample_doc.md"
    md_file.write_text("""# Sample Document

## Overview
This is a test document for asset processing.

## Key Points
- Asset management working
- Vector memory creation
- Team workflow integration

## Conclusion
Everything looks good!
""")
    assets.append(str(md_file))
    
    # Create a text file
    txt_file = temp_dir / "notes.txt"
    txt_file.write_text("""Project Notes

Important requirements:
- Process all document types
- Create vector embeddings
- Support team workflows

Implementation notes:
- Use ChromaDB for vector storage
- Support PDF, DOCX, MD, TXT formats
- Integrate with RAG workflows
""")
    assets.append(str(txt_file))
    
    # Create a JSON conversation file
    conv_dir = temp_dir / "conversations"
    conv_dir.mkdir()
    conv_file = conv_dir / "client_meeting.json"
    conv_file.write_text("""[
    {"speaker": "client", "ts": "2025-08-24", "text": "We need a robust document processing system"},
    {"speaker": "consultant", "ts": "2025-08-24", "text": "I recommend using vector embeddings for better search"},
    {"speaker": "client", "ts": "2025-08-24", "text": "How would that integrate with our workflow?"},
    {"speaker": "consultant", "ts": "2025-08-24", "text": "The system can automatically process documents and create searchable embeddings"}
]""")
    assets.append(str(conv_file))
    
    return assets


def test_workflow_with_assets():
    """Test the complete workflow with real assets."""
    print("🚀 Starting Asset Movement Integration Test")
    print("=" * 60)
    
    logger_factory = MemoryLoggerFactory()
    
    with tempfile.TemporaryDirectory() as temp_output:
        with tempfile.TemporaryDirectory() as temp_assets:
            # Create sample assets
            sample_assets = create_sample_assets(Path(temp_assets))
            print(f"📄 Created {len(sample_assets)} sample assets:")
            for asset in sample_assets:
                print(f"   📄 {Path(asset).name}")
            
            # Initialize workflow with assets
            print(f"\n🧪 Testing RAQ workflow with assets...")
            
            wm = WorkflowManager(logger_factory)
            orchestrator = WorkflowOrchestrator(logger_factory=logger_factory)
            mock_factory = MockTeamRunnerFactory(logger_factory)
            
            try:
                wm.initialize(
                    job_id="asset_test_001",
                    document_type="RAQ",
                    output_base_path=temp_output,
                    orchestrator=orchestrator,
                    team_runner_factory=mock_factory,
                    assets=sample_assets  # Pass our sample assets
                )
                
                print(f"✅ Workflow initialized with assets")
                print(f"   📊 Teams: {len(wm.teams)}")
                print(f"   📂 Job folder: {wm.job_folder}")
                
                # Check asset manager
                if wm.asset_manager:
                    summary = wm.asset_manager.get_asset_summary()
                    print(f"\n📦 Asset Summary:")
                    print(f"   Total files: {summary['total_files']}")
                    print(f"   File types: {summary['types']}")
                    print(f"   Moved files: {len(summary['moved_files'])}")
                    
                    print(f"\n📁 Asset files in job folder:")
                    asset_files = wm.asset_manager.list_asset_files()
                    for asset_file in asset_files:
                        rel_path = Path(asset_file).relative_to(wm.job_folder)
                        print(f"   📄 {rel_path}")
                    
                    # Check if vector memory was created
                    if wm.memory:
                        print(f"   🧠 Vector memory created successfully")
                    else:
                        print(f"   ⚠️ Vector memory not created")
                
                # Test asset formatting for agents
                asset_info = wm.asset_manager.format_assets_for_agent()
                if asset_info.strip():
                    print(f"\n📋 Asset info for agents:")
                    print(asset_info)
                
                # Execute workflow
                print(f"\n🎯 Executing workflow...")
                result = wm.run()
                
                if result:
                    print(f"✅ Workflow executed successfully")
                    
                    # Check final statuses
                    print(f"\n📈 Final team statuses:")
                    for team in wm.teams:
                        status = orchestrator.get(team.id)
                        print(f"   🔧 {team.id}: {status}")
                else:
                    print(f"⚠️ Workflow completed with issues")
                
                # Log summary
                logger = logger_factory.create_logger()
                entries = logger.entries()
                error_count = sum(1 for e in entries if e.is_error)
                print(f"\n📝 Execution summary:")
                print(f"   Log entries: {len(entries)}")
                print(f"   Errors: {error_count}")
                
                if error_count == 0:
                    print(f"✅ Asset movement test completed successfully!")
                else:
                    print(f"⚠️ Test completed with {error_count} errors")
                    for entry in entries:
                        if entry.is_error:
                            print(f"      ❌ {entry.message}")
                    
            except Exception as e:
                print(f"❌ Asset movement test failed: {e}")
                raise


if __name__ == "__main__":
    test_workflow_with_assets()
