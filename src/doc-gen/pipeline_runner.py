#!/usr/bin/env python3
"""
Pipeline Runner for Document Generation Service

This module contains the core pipeline orchestration logic with support for 
parallel execution and dependency-based workflow management.

Features:
- Parallel team execution with dependency resolution
- Dynamic workflow configuration loading
- Job-based execution with asset management
- Cancellation support and error handling
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from datetime import datetime

# Local imports
from workflow_manager import WorkflowManager
from job_manager import JobManager
from team_executor import TeamExecutor
from step_utils import prepare_step_file_summaries, prepare_agent_result_content
from asset_manager import AssetManager


class PipelineRunner:
    """Orchestrates parallel workflow execution with dependency management."""
    
    def __init__(self, base_dir: Path = None, cancellation_flag=None):
        self.base_dir = base_dir or Path(__file__).parent
        self.cancellation_flag = cancellation_flag
        
        # Initialize managers
        self.workflow_manager = WorkflowManager(self.base_dir)
        self.job_manager = JobManager(self.base_dir)
        self.team_executor = TeamExecutor(self.base_dir)
        
        # Runtime state
        self.asset_manager = None
        self.memory = None
    
    async def run_pipeline(self, job_id: str, user_input: str, template_url: Optional[str], 
                          document_type: str, output_base_path: Path, 
                          assets: Optional[List[str]] = None, last_team_executed: Optional[str] = None, 
                          source_job_id: Optional[str] = None) -> bool:
        """Run the complete pipeline with parallel execution support."""
        
        print(f"=== AutoGen Pipeline Runner ===")
        print(f"Job ID: {job_id}")
        print(f"Document Type: {document_type}")
        
        try:
            # Set document type and load workflow configuration
            self.workflow_manager.set_document_type(document_type)
            
            # Create job folder
            job_folder = self.job_manager.create_job_folder(job_id, output_base_path)
            
            # Handle source job copying if needed
            if source_job_id and last_team_executed:
                source_job_folder = output_base_path / source_job_id
                self.job_manager.copy_job_assets(job_folder, source_job_folder)
            
            # Setup asset memory if assets provided
            if assets:
                await self._setup_asset_memory(job_id, job_folder, assets)
            
            # Copy workflow assets to job folder
            self.job_manager.copy_workflow_assets(
                job_folder, document_type, template_url, user_input,
                self.workflow_manager.workflow_config
            )
            
            # Execute workflow with parallel support
            success = await self._execute_parallel_workflow(
                job_folder, job_id, user_input, template_url, document_type, last_team_executed
            )
            
            if success:
                print(f"\n✨ Pipeline completed successfully!")
                print(f"Job folder: {job_folder}")
            
            return success
            
        except Exception as e:
            print(f"Pipeline execution failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _setup_asset_memory(self, job_id: str, job_folder: Path, assets: List[str]):
        """Setup asset memory for vector-enabled teams."""
        print(f"Setting up assets and vector memory for {len(assets)} asset(s)")
        
        try:
            self.asset_manager = AssetManager(job_id, str(job_folder), assets)
            self.memory = await self.asset_manager.create_vector_memory()
            
            if self.memory:
                print("✅ Asset memory configured for agents")
            else:
                print("⚠️ Asset memory setup failed")
                
        except Exception as e:
            print(f"Error setting up asset memory: {e}")
    
    async def _execute_parallel_workflow(self, job_folder: Path, job_id: str, user_input: str, 
                                       template_url: Optional[str], document_type: str, 
                                       last_team_executed: Optional[str] = None) -> bool:
        """Execute workflow with parallel team execution based on dependencies."""
        
        print(f"\n=== Executing Parallel Workflow ===")
        
        # Get execution plan
        try:
            execution_plan = self.workflow_manager.get_execution_plan(last_team_executed)
        except ValueError as e:
            print(f"Error creating execution plan: {e}")
            return False
        
        if not execution_plan:
            print("No teams to execute")
            return True
        
        # Track execution state
        completed_teams = set()
        team_outputs = {}
        
        # Mark last executed team as completed if resuming
        if last_team_executed:
            completed_teams.add(last_team_executed)
            print(f"Resuming from: {last_team_executed}")
        
        # Execute phases sequentially, teams within each phase in parallel
        for phase_num, phase_teams in enumerate(execution_plan, 1):
            print(f"\n--- Phase {phase_num}: {[t['name'] for t in phase_teams]} ---")
            
            # Check for cancellation before each phase
            if self.cancellation_flag and self.cancellation_flag.is_set():
                print(f"⚠️ Pipeline cancelled before phase {phase_num}")
                return False
            
            # Execute teams in this phase in parallel
            phase_results = await self._execute_phase_parallel(
                phase_teams, job_folder, job_id, user_input, template_url, 
                document_type, team_outputs, completed_teams
            )
            
            # Check results and update state
            phase_success = True
            for team_name, (success, output_path) in phase_results.items():
                if success:
                    completed_teams.add(team_name)
                    team_outputs[team_name] = output_path
                    print(f"✅ {team_name} completed successfully")
                else:
                    print(f"❌ {team_name} failed")
                    phase_success = False
            
            if not phase_success:
                print(f"Phase {phase_num} failed - stopping execution")
                return False
        
        print(f"\n🎉 All phases completed successfully!")
        return True
    
    async def _execute_phase_parallel(self, phase_teams: List[Dict[str, Any]], job_folder: Path, 
                                    job_id: str, user_input: str, template_url: Optional[str], 
                                    document_type: str, team_outputs: Dict[str, Path], 
                                    completed_teams: Set[str]) -> Dict[str, tuple]:
        """Execute teams in a phase in parallel."""
        
        # Prepare tasks for parallel execution
        tasks = []
        for team_config in phase_teams:
            task = self._create_team_execution_task(
                team_config, job_folder, job_id, user_input, template_url, 
                document_type, team_outputs, completed_teams
            )
            tasks.append(task)
        
        # Execute teams in parallel
        if len(tasks) == 1:
            # Single team - execute directly
            team_name = phase_teams[0]['name']
            result = await tasks[0]
            return {team_name: result}
        else:
            # Multiple teams - execute in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            phase_results = {}
            for i, result in enumerate(results):
                team_name = phase_teams[i]['name']
                if isinstance(result, Exception):
                    print(f"❌ {team_name} failed with exception: {result}")
                    phase_results[team_name] = (False, None)
                else:
                    phase_results[team_name] = result
            
            return phase_results
    
    async def _create_team_execution_task(self, team_config: Dict[str, Any], job_folder: Path, 
                                        job_id: str, user_input: str, template_url: Optional[str], 
                                        document_type: str, team_outputs: Dict[str, Path], 
                                        completed_teams: Set[str]):
        """Create an async task for team execution."""
        
        team_name = team_config['name']
        
        # Prepare team inputs
        input_files = self.job_manager.prepare_team_input_files(team_config, team_outputs, job_folder)
        step_summaries = prepare_step_file_summaries(str(job_folder), team_name, team_config.get('step_files', []))
        agent_result_content = prepare_agent_result_content(team_config, job_folder)
        
        # Create output file paths
        output_prefix = team_config['output_file']
        output_file = job_folder / f"{output_prefix}.md"
        
        # Team configuration file
        team_yaml = job_folder / f"{team_name}.yaml"
        
        # Convert single template_url to list format for external URLs
        external_urls = [template_url] if template_url else []
        
        # Execute team
        print(f"🚀 Starting {team_name}...")
        success = await self.team_executor.execute_team(
            team_yaml,
            output_file,
            team_name.replace('_', ' ').replace('Content ', 'Content '),
            job_id,
            user_input,
            external_urls,
            document_type,
            job_folder,
            input_files=input_files,
            step_summaries=step_summaries,
            agent_result_content=agent_result_content,
            memory=self.memory,
            cancellation_flag=self.cancellation_flag
        )
        
        return (success, output_file if success else None)
    
    async def run_planning_only(self, job_id: str, user_input: str, template_url: Optional[str], 
                               document_type: str, output_base_path: Path) -> bool:
        """Run only the planning pipeline for a specific job."""
        print(f"=== AutoGen Planning Pipeline Runner ===")
        print(f"Job ID: {job_id}")
        print(f"Document Type: {document_type}")
        
        # This is a simplified version - could be enhanced to use the workflow system
        # For now, maintaining compatibility with existing functionality
        return await self.run_pipeline(
            job_id, user_input, template_url, document_type, output_base_path
        )
    
    def run_production_only(self, job_id: str, planning_file_path: str) -> bool:
        """Run only the content production workflow using provided planning output."""
        print(f"=== AutoGen Production-Only Pipeline ===")
        print(f"Job ID: {job_id}")
        print(f"Planning Input: {planning_file_path}")
        
        # This would need to be enhanced to work with the new parallel system
        # For now, maintaining basic compatibility
        try:
            source_job_folder = Path(planning_file_path).parent
            planning_output = Path(planning_file_path)
            
            if not planning_output.exists():
                print(f"Error: Planning file not found: {planning_file_path}")
                return False
            
            # Create new job folder for production-only run
            output_base_path = source_job_folder.parent
            new_job_folder = self.job_manager.create_job_folder(job_id, output_base_path)
            
            # Clone assets from source job
            source_assets_dir = source_job_folder / "assets"
            if source_assets_dir.exists():
                import shutil
                target_assets_dir = new_job_folder / "assets"
                shutil.copytree(source_assets_dir, target_assets_dir, dirs_exist_ok=True)
            
            # Copy planning output
            new_planning_path = new_job_folder / "planning_output.md"
            import shutil
            shutil.copy2(planning_output, new_planning_path)
            
            print(f"Production-only setup completed for job {job_id}")
            return True
            
        except Exception as e:
            print(f"Error in production-only pipeline: {e}")
            return False
