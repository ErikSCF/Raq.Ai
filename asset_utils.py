"""
Asset management utilities for RAQ pipeline.
Handles loading, moving, and processing of assets (PDFs, meeting notes, transcripts, etc.)
"""

import os
import shutil
from pathlib import Path
import glob
from typing import List, Dict, Any

def get_assets_directory() -> str:
    """Get the root assets directory path."""
    return os.path.join(os.path.dirname(__file__), "assets")

def get_output_assets_directory(job_id: str) -> str:
    """Get the output assets directory for a specific job."""
    return os.path.join(os.path.dirname(__file__), "output", job_id, "assets")

def list_available_assets() -> List[str]:
    """List all available assets in the root assets directory."""
    assets_dir = get_assets_directory()
    if not os.path.exists(assets_dir):
        return []
    
    # Look for all common document types
    patterns = ["*.pdf", "*.txt", "*.md", "*.docx", "*.doc", "*.pptx", "*.ppt"]
    assets = []
    
    for pattern in patterns:
        assets.extend(glob.glob(os.path.join(assets_dir, pattern)))
    
    return [os.path.basename(asset) for asset in assets]

def move_assets_to_job(job_id: str) -> List[str]:
    """
    Move assets from root assets directory to job-specific output directory.
    Returns list of moved asset filenames.
    """
    source_dir = get_assets_directory()
    target_dir = get_output_assets_directory(job_id)
    
    # Create target directory if it doesn't exist
    os.makedirs(target_dir, exist_ok=True)
    
    moved_assets = []
    available_assets = list_available_assets()
    
    for asset_name in available_assets:
        source_path = os.path.join(source_dir, asset_name)
        target_path = os.path.join(target_dir, asset_name)
        
        try:
            shutil.copy2(source_path, target_path)
            moved_assets.append(asset_name)
            print(f"Moved asset: {asset_name}")
        except Exception as e:
            print(f"Error moving asset {asset_name}: {e}")
    
    return moved_assets

def clone_assets_from_job(source_job_id: str, target_job_id: str) -> List[str]:
    """
    Clone assets from a source job to target job directory.
    Used when running production-only with existing job assets.
    """
    source_dir = get_output_assets_directory(source_job_id)
    target_dir = get_output_assets_directory(target_job_id)
    
    if not os.path.exists(source_dir):
        print(f"No assets found for job {source_job_id}")
        return []
    
    # Create target directory if it doesn't exist
    os.makedirs(target_dir, exist_ok=True)
    
    cloned_assets = []
    
    # Copy all files from source to target
    for filename in os.listdir(source_dir):
        source_path = os.path.join(source_dir, filename)
        target_path = os.path.join(target_dir, filename)
        
        if os.path.isfile(source_path):
            try:
                shutil.copy2(source_path, target_path)
                cloned_assets.append(filename)
                print(f"Cloned asset: {filename}")
            except Exception as e:
                print(f"Error cloning asset {filename}: {e}")
    
    return cloned_assets

def read_text_file(file_path: str) -> str:
    """Read content from a text file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"Error reading text file {file_path}: {e}")
        return ""

def load_asset_content(file_path: str) -> str:
    """
    Load content from an asset file.
    For text files (.txt, .md): reads content directly
    For other files: returns file path for agent processing
    """
    if not os.path.exists(file_path):
        return ""
    
    file_extension = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)
    
    if file_extension in ['.txt', '.md']:
        content = read_text_file(file_path)
        return f"TEXT CONTENT FROM {filename}:\n{content}\n"
    else:
        # For PDFs, DOCX, etc., let the agent know the file is available
        return f"ASSET FILE AVAILABLE: {filename} (Type: {file_extension})\nPath: {file_path}\nNote: This file should be processed directly by the agent.\n"

def load_all_job_assets(job_id: str) -> Dict[str, str]:
    """
    Load content from all assets in a job directory.
    Returns dictionary mapping filename to content.
    """
    assets_dir = get_output_assets_directory(job_id)
    assets_content = {}
    
    if not os.path.exists(assets_dir):
        return assets_content
    
    for filename in os.listdir(assets_dir):
        file_path = os.path.join(assets_dir, filename)
        if os.path.isfile(file_path):
            content = load_asset_content(file_path)
            if content:
                assets_content[filename] = content
    
    return assets_content

def format_assets_for_agent(assets_content: Dict[str, str]) -> str:
    """
    Format asset content for inclusion in agent context.
    Creates a structured summary of all assets.
    """
    if not assets_content:
        return "No additional assets provided for this project."
    
    formatted_content = "ADDITIONAL PROJECT ASSETS:\n\n"
    
    text_files = []
    other_files = []
    
    for filename, content in assets_content.items():
        if content.startswith("TEXT CONTENT FROM"):
            text_files.append((filename, content))
        else:
            other_files.append((filename, content))
    
    # Add text content first
    if text_files:
        formatted_content += "=== TEXT-BASED ASSETS ===\n"
        for filename, content in text_files:
            formatted_content += content + "\n"
    
    # Add file references for other assets
    if other_files:
        formatted_content += "=== OTHER ASSETS AVAILABLE ===\n"
        for filename, content in other_files:
            formatted_content += content + "\n"
    
    formatted_content += "=== END OF ASSETS ===\n"
    
    return formatted_content

def get_assets_summary(job_id: str) -> str:
    """Get a summary of assets available for a job."""
    assets_dir = get_output_assets_directory(job_id)
    
    if not os.path.exists(assets_dir):
        return "No assets directory found for this job."
    
    files = [f for f in os.listdir(assets_dir) if os.path.isfile(os.path.join(assets_dir, f))]
    
    if not files:
        return "No assets found for this job."
    
    return f"Assets available ({len(files)} files): {', '.join(files)}"
