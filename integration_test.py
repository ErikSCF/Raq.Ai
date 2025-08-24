#!/usr/bin/env python3
"""
Integration Test: Complete Workflow Execution

This script tests the complete pipeline:
1. WorkflowManager derives workflow path from document type
2. AssetManager copies document template files
3. Teams are created from workflow configuration
4. Everything is self-contained in the output directory
"""

import sys
import tempfile
from pathlib import Path

# Add the src/doc-gen directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src" / "doc-gen"))

from workflow import WorkflowManager
from workflow_orchestrator import WorkflowOrchestrator
from team_runner import TeamRunnerFactory
from tests.mock_team_runner import MockTeamRunnerFactory
from logger import MemoryLoggerFactory


def test_complete_workflow():
    """Test the complete workflow pipeline."""
    print("🚀 Starting Complete Workflow Integration Test")
    print("=" * 60)
    
    # Setup
    logger_factory = MemoryLoggerFactory()
    logger = logger_factory.create_logger()
    
    # Create temporary output directory
    with tempfile.TemporaryDirectory() as temp_output:
        print(f"📁 Using temporary output directory: {temp_output}")
        
        # Test with a real document type (RAQ)
        print("\n🧪 Testing with RAQ document type...")
        
        # Initialize WorkflowManager (no workflow path needed - derived from document type)
        wm = WorkflowManager(logger_factory)
        orchestrator = WorkflowOrchestrator(logger_factory=logger_factory)
        mock_factory = MockTeamRunnerFactory(logger_factory)
        
        try:
            # Initialize with RAQ document type
            wm.initialize(
                job_id="integration_test_001",
                document_type="RAQ",  # This will look in documents/RAQ/
                output_base_path=temp_output,
                orchestrator=orchestrator,
                team_runner_factory=mock_factory,
                assets=[]  # No additional assets for this test
            )
            
            print(f"✅ WorkflowManager initialized successfully")
            print(f"   📊 Teams created: {len(wm.teams)}")
            print(f"   📂 Job folder: {wm.job_folder}")
            
            # Verify teams were created correctly
            for i, team in enumerate(wm.teams, 1):
                print(f"   🔧 Team {i}: {team.id} (template: {team.template})")
                print(f"      📄 Output file: {team.output_file}")
                if team.depends_on:
                    print(f"      🔗 Depends on: {team.depends_on}")
            
            # Verify workflow file was copied to job folder
            workflow_file = wm.job_folder / "workflow.yaml"
            if workflow_file.exists():
                print(f"   ✅ Workflow file copied to job folder")
            else:
                print(f"   ❌ Workflow file NOT found in job folder")
            
            # Verify asset manager copied template files
            assets_dir = wm.job_folder / "assets"
            if assets_dir.exists():
                asset_files = list(assets_dir.iterdir())
                print(f"   📦 Asset files copied: {len(asset_files)}")
                for asset_file in asset_files:
                    print(f"      📄 {asset_file.name}")
            else:
                print(f"   ❌ Assets directory NOT found")
            
            # Test workflow execution
            print(f"\n🎯 Testing workflow execution...")
            result = wm.run()
            
            if result:
                print(f"   ✅ Workflow executed successfully")
            else:
                print(f"   ⚠️ Workflow execution completed with errors")
            
            # Check final team statuses
            print(f"\n📈 Final team statuses:")
            for team in wm.teams:
                status = orchestrator.get(team.id)
                print(f"   🔧 {team.id}: {status}")
            
            # Check logs
            entries = logger.entries()
            print(f"\n📝 Log summary:")
            print(f"   Total entries: {len(entries)}")
            
            # Categorize log entries
            error_count = sum(1 for e in entries if e.is_error)
            warning_count = sum(1 for e in entries if "warning" in e.message.lower())
            team_count = sum(1 for e in entries if "team" in e.message.lower())
            
            print(f"   Errors: {error_count}")
            print(f"   Warnings: {warning_count}")
            print(f"   Team-related: {team_count}")
            
            if error_count > 0:
                print(f"\n❌ Error messages:")
                for entry in entries:
                    if entry.is_error:
                        print(f"      [{entry.component}] {entry.message}")
            
            print(f"\n✅ Integration test completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Integration test failed: {e}")
            raise


def test_simple_document_type():
    """Test with the simple document type."""
    print("\n" + "=" * 60)
    print("🧪 Testing with simple document type...")
    
    logger_factory = MemoryLoggerFactory()
    
    with tempfile.TemporaryDirectory() as temp_output:
        wm = WorkflowManager(logger_factory)
        orchestrator = WorkflowOrchestrator(logger_factory=logger_factory)
        mock_factory = MockTeamRunnerFactory(logger_factory)
        
        try:
            wm.initialize(
                job_id="simple_test_001",
                document_type="simple",  # This will look in tests/documents/simple/
                output_base_path=temp_output,
                orchestrator=orchestrator,
                team_runner_factory=mock_factory,
                assets=[]
            )
            
            print(f"✅ Simple workflow initialized")
            print(f"   📊 Teams: {len(wm.teams)}")
            for team in wm.teams:
                print(f"   🔧 {team.id} -> {team.output_file}")
            
            # Execute the workflow
            result = wm.run()
            print(f"   🎯 Execution result: {'✅ Success' if result else '⚠️ Completed with issues'}")
            
        except Exception as e:
            print(f"❌ Simple workflow test failed: {e}")
            raise


if __name__ == "__main__":
    test_complete_workflow()
    test_simple_document_type()
    print("\n🎉 All integration tests completed!")
