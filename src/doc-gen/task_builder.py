#!/usr/bin/env python3
"""
Task Builder for Document Generation Pipeline

This module handles task message preparation and input content processing.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List


class TaskBuilder:
    """Builds task messages and processes input content for teams."""
    
    def __init__(self):
        pass
    
    def prepare_task_message(self, job_id: str, user_input: str, external_urls: Optional[List[str]], 
                           document_type: str, team_name: str, job_folder: Optional[Path], 
                           input_files: Optional[List[str]], asset_manager=None, 
                           brief_content: str = "") -> str:
        """Prepare task message with all relevant context and input files."""
        
        # Load assets for this job if available
        assets_formatted = ""
        if job_folder and asset_manager:
            assets_formatted = asset_manager.format_assets_for_agent()
        
        # Generic task message preparation - no hardcoded team names
        task_parts = [
            f"Document Type: {document_type}",
            f"Content Description: {user_input}"
        ]
        
        # Add content brief if available
        if brief_content:
            task_parts.append(f"\nSTART CONTENT BRIEF:\n{brief_content}")
            task_parts.append(f"\nEND CONTENT BRIEF")
        
        # Add assets if available
        if assets_formatted:
            task_parts.append(f"\n{assets_formatted}")
        
        # Add external URLs if provided (teams can use for templates, references, APIs, etc.)
        if external_urls:
            for i, url in enumerate(external_urls):
                task_parts.append(f"\nExternal URL {i+1}: {url}")
        
        # Handle input files
        if input_files:
            for file_path in input_files:
                if job_folder:
                    full_file_path = job_folder / file_path
                    if full_file_path.exists():
                        try:
                            # Check file size to decide whether to include content or just reference
                            file_size = full_file_path.stat().st_size
                            size_kb = file_size / 1024
                            
                            if size_kb > 50.0:  # Files larger than 50KB - just reference
                                task_parts.append(f"\n=== INPUT FILE REFERENCE ===\nFile: {full_file_path.name}\nSize: {size_kb:.1f} KB\nPath: {file_path}")
                                print(f"  ✓ Added file reference: {full_file_path.name} ({size_kb:.1f} KB)")
                            else:  # Smaller files - include content
                                with open(full_file_path, 'r', encoding='utf-8') as f:
                                    file_content = f.read()
                                    # Remove TERMINATE to prevent premature termination
                                    file_content = file_content.replace('TERMINATE', '').strip()
                                    
                                task_parts.append(f"\n=== INPUT FILE CONTENT ===\n{file_content}")
                                print(f"  ✓ Added file content: {full_file_path.name}")
                        except Exception as e:
                            print(f"  ⚠ Could not process file {full_file_path}: {e}")
        
        # Generic workflow start message
        task_parts.append(f"\nPlease begin the {team_name.replace('_', ' ')} workflow.")
        
        return "\n".join(task_parts)
    
    def load_content_brief(self, document_type: str, job_folder: Optional[Path]) -> str:
        """Load the content brief file if available."""
        brief_content = ""
        
        # Use the standard content brief from the job folder (already copied by copy_assets)
        if document_type != 'Unknown':
            brief_path = job_folder / "brand_content_brief.md" if job_folder else None
            if brief_path and brief_path.exists():
                with open(brief_path, 'r', encoding='utf-8') as f:
                    brief_content = f.read()
                print(f"Using document type content brief: {document_type}")
            else:
                print(f"Warning: Content brief file not found: {brief_path}")
        
        return brief_content
    
    def prepare_template_variables(self, selector_prompt: str, input_files: List[str], 
                                 step_summaries: str, agent_result_content: str) -> str:
        """Prepare template variables for selector prompt injection."""
        
        # Handle template variable replacements - preserve AutoGen's built-ins
        if '{input_files}' in selector_prompt:
            selector_prompt = selector_prompt.replace('{input_files}', str(input_files))
        
        # Inject step summaries (agent flows from previous teams)
        if '{step_summaries}' in selector_prompt and step_summaries:
            selector_prompt = selector_prompt.replace('{step_summaries}', step_summaries)
        
        # Inject agent result (final output from previous team)
        if '{agent_result}' in selector_prompt and agent_result_content:
            selector_prompt = selector_prompt.replace('{agent_result}', agent_result_content)
        
        return selector_prompt
    
    def inject_agent_context(self, system_message: str, step_summaries: str, 
                           agent_result_content: str) -> str:
        """Inject context into agent system messages."""
        
        # Inject step summaries into agent system messages for analysis teams
        if '{step_summaries}' in system_message and step_summaries:
            system_message = system_message.replace('{step_summaries}', step_summaries)
        
        # Inject agent result content into agent system messages
        if '{agent_result}' in system_message and agent_result_content:
            system_message = system_message.replace('{agent_result}', agent_result_content)
        
        return system_message
