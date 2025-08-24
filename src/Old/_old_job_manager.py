#!/usr/bin/env python3
"""
Job Manager for Document Generation Pipeline

This module handles job folder creation, asset management, and file operations.
"""

import shutil
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class JobManager:
    """Manages job folders, asset copying, and file operations."""
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent
        self.documents_dir = self.base_dir / "documents"
    
    def create_job_folder(self, job_id: str, output_base_path: Path) -> Path:
        """Create a job-specific folder."""
        job_folder = output_base_path / job_id
        job_folder.mkdir(parents=True, exist_ok=True)
        return job_folder
    
    def copy_job_assets(self, job_folder: Path, source_job_folder: Path):
        """Copy files from source job to new job folder."""
        if not source_job_folder.exists():
            print(f"⚠️  Warning: Source job folder {source_job_folder} not found")
            return
        
        print(f"📋 Copying files from source job {source_job_folder.name} to job {job_folder.name}")
        
        # Copy all files from source job
        for item in source_job_folder.iterdir():
            if item.is_file():
                dest_path = job_folder / item.name
                shutil.copy2(item, dest_path)
                print(f"   Copied: {item.name}")
            elif item.is_dir() and item.name == "assets":
                # Copy assets directory
                dest_assets = job_folder / "assets"
                if dest_assets.exists():
                    shutil.rmtree(dest_assets)
                shutil.copytree(item, dest_assets)
                print(f"   Copied: assets/ directory")
        
        print(f"✅ Source job files copied successfully")
    
    def copy_workflow_assets(self, job_folder: Path, document_type: str, 
                           template_url: Optional[str], user_input: str,
                           workflow_config: Dict[str, Any]):
        """Copy all relevant workflow assets to the job folder."""
        
        document_type_dir = self.documents_dir / document_type
        
        # Copy all team YAML files from the document type directory
        for team in workflow_config['workflow']['teams']:
            team_file = f"{team['name']}.yaml"
            source_path = document_type_dir / team_file
            dest_path = job_folder / team_file
            shutil.copy2(source_path, dest_path)
            print(f"✓ Copied team config: {team_file}")
        
        # Copy workflow configuration
        workflow_dest = job_folder / "workflow.yaml"
        shutil.copy2(document_type_dir / "workflow.yaml", workflow_dest)
        print(f"✓ Copied workflow config: workflow.yaml")
        
        # Copy the content brief from the document type folder
        brief_source = document_type_dir / "brand_content_brief.md"
        print(f"DEBUG: Looking for content brief file: {brief_source}")
        print(f"DEBUG: File exists: {brief_source.exists()}")
        
        if brief_source.exists():
            brief_dest = job_folder / f"content_brief_{document_type}.md"
            shutil.copy2(brief_source, brief_dest)
            print(f"DEBUG: Copied to: {brief_dest}")
            
            # Also save as the standard name that agents expect to reference
            standard_brief_dest = job_folder / "brand_content_brief.md"
            shutil.copy2(brief_source, standard_brief_dest)
            print(f"Saved content brief as: {standard_brief_dest}")
        else:
            print(f"Warning: Content brief file not found: {brief_source}")
            available_types = [d.name for d in self.documents_dir.iterdir() if d.is_dir()]
            print(f"Available document types: {available_types}")
        
        # Create pipeline configuration file
        config_data = {
            "job_id": job_folder.name,
            "document_type": document_type,
            "workflow_name": workflow_config['workflow']['name'],
            "template_url": template_url,
            "user_input": user_input,
            "timestamp": datetime.now().isoformat()
        }
        
        config_file = job_folder / "pipeline_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        print(f"Copied assets to: {job_folder}")
        return job_folder / "workflow.yaml"
    
    def prepare_team_input_files(self, team_config: Dict, team_outputs: Dict[str, Path], job_folder: Path) -> List[str]:
        """Prepare input files list for a team based on its configuration."""
        input_files = []
        
        for input_field in team_config.get('input_files', []):
            # All items in input_files should be file patterns or references
            if input_field.endswith("_artifacts"):
                # Dynamic pattern: "{teamname}_artifacts" -> look up team output
                # e.g., "epic_discovery_artifacts" -> Epic_Discovery_Team output
                team_prefix = input_field.replace("_artifacts", "")
                
                # Convert snake_case to Team_Name format
                team_name_parts = team_prefix.split("_")
                team_name_formatted = "_".join(word.capitalize() for word in team_name_parts) + "_Team"
                
                # Look for the team output
                team_output = team_outputs.get(team_name_formatted)
                if team_output:
                    input_files.append(str(team_output.relative_to(job_folder)))
                    print(f"  ✓ Mapped {input_field} -> {team_name_formatted} output: {team_output.name}")
                else:
                    print(f"  ⚠ No output found for {input_field} (looking for {team_name_formatted})")
            elif "*" in input_field or "?" in input_field:
                # Glob pattern support - find files matching the pattern
                import glob
                from pathlib import Path
                
                # Use glob to find matching files in the job folder
                pattern_path = job_folder / input_field
                matching_files = glob.glob(str(pattern_path))
                
                if matching_files:
                    # Convert to relative paths from job folder
                    relative_files = [str(Path(f).relative_to(job_folder)) for f in matching_files]
                    input_files.extend(relative_files)
                    print(f"  ✓ Glob {input_field} matched: {relative_files}")
                else:
                    print(f"  ⚠ Glob pattern {input_field} found no matches in {job_folder}")
            else:
                # Handle literal file paths - check if file exists in job folder
                file_path = job_folder / input_field
                if file_path.exists():
                    input_files.append(str(file_path.relative_to(job_folder)))
                    print(f"  ✓ Literal file {input_field} found: {file_path.name}")
                else:
                    print(f"  ⚠ Literal file {input_field} not found in {job_folder}")
        
        return input_files
    
    def extract_brand_brief_from_planning(self, planning_file: Path, job_folder: Path):
        """Extract brand content brief from planning output for production team use."""
        try:
            with open(planning_file, 'r', encoding='utf-8') as f:
                planning_content = f.read()
            
            # Look for brand content brief section
            lines = planning_content.split('\n')
            brief_lines = []
            in_brief_section = False
            
            for line in lines:
                if "START CONTENT BRIEF" in line.upper():
                    in_brief_section = True
                    continue
                elif in_brief_section and line.strip() == "END CONTENT BRIEF":
                    break
                elif in_brief_section:
                    brief_lines.append(line)
            
            # Save extracted brief
            if brief_lines:
                brand_brief_path = job_folder / "brand_content_brief.md"
                with open(brand_brief_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(brief_lines).strip())
                print(f"✓ Extracted brand content brief to {brand_brief_path}")
            
        except Exception as e:
            print(f"Warning: Could not extract brand content brief: {e}")
    
    def copy_production_assets(self, job_folder: Path, base_dir: Path) -> Path:
        """Copy only the assets needed for production team execution."""
        try:
            # Copy production team YAML
            production_yaml = base_dir / "Content_Production_Team.yaml"
            production_yaml_dest = job_folder / "Content_Production_Team.yaml"
            shutil.copy2(production_yaml, production_yaml_dest)
            
            # Copy tools config
            tools_config_path = base_dir / "tools_config.yaml"
            tools_config_dest = job_folder / "tools_config.yaml"
            shutil.copy2(tools_config_path, tools_config_dest)
            
            # Note: In production-only mode, we don't extract brand content brief
            # since it's already included in the planning output file that will be used
            
            return production_yaml_dest
            
        except Exception as e:
            print(f"Error copying production assets: {e}")
            raise
