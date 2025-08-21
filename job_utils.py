#!/usr/bin/env python3
"""
Job ID Utilities for RAQ.AI Document Generation Service

This module provides functions for managing sequential job IDs stored in jobid.txt.
"""

from pathlib import Path

def get_next_job_id(base_path: Path = None) -> str:
    """
    Get the next sequential job ID from jobid.txt file.
    Creates the file with '0001' if it doesn't exist.
    
    Args:
        base_path: Base directory where jobid.txt is located. Defaults to current file's parent.
        
    Returns:
        str: Next job ID as a 4-digit string (e.g., "0003")
    """
    if base_path is None:
        base_path = Path.cwd()
    
    jobid_file = base_path / "jobid.txt"
    
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

def peek_current_job_id(base_path: Path = None) -> str:
    """
    Peek at the current job ID without incrementing.
    
    Args:
        base_path: Base directory where jobid.txt is located. Defaults to current file's parent.
        
    Returns:
        str: Current job ID as a 4-digit string. Returns '0001' if file doesn't exist.
    """
    if base_path is None:
        base_path = Path.cwd()
    
    jobid_file = base_path / "jobid.txt"
    
    if not jobid_file.exists():
        return "0001"
    
    with open(jobid_file, 'r') as f:
        return f.read().strip()

def get_next_job_id_without_increment(base_path: Path = None) -> str:
    """
    Get what the next job ID would be without actually incrementing the counter.
    
    Args:
        base_path: Base directory where jobid.txt is located. Defaults to current file's parent.
        
    Returns:
        str: What the next job ID would be as a 4-digit string.
    """
    current = peek_current_job_id(base_path)
    next_id = int(current) + 1
    return f"{next_id:04d}"

def reset_job_id(start_id: str = "0001", base_path: Path = None) -> None:
    """
    Reset the job ID counter to a specific value.
    
    Args:
        start_id: The job ID to reset to (e.g., "0001")
        base_path: Base directory where jobid.txt is located. Defaults to current file's parent.
    """
    if base_path is None:
        base_path = Path.cwd()
    
    jobid_file = base_path / "jobid.txt"
    
    with open(jobid_file, 'w') as f:
        f.write(start_id)

def get_job_history(output_path: Path, base_path: Path = None) -> dict:
    """
    Get information about existing job folders and current job ID state.
    
    Args:
        output_path: Path to the output directory containing job folders
        base_path: Base directory where jobid.txt is located. Defaults to current file's parent.
        
    Returns:
        dict: Dictionary containing job history information
    """
    if base_path is None:
        base_path = Path.cwd()
    
    current_id = peek_current_job_id(base_path)
    next_id = get_next_job_id_without_increment(base_path)
    
    job_folders = []
    if output_path.exists():
        job_folders = [d for d in output_path.iterdir() if d.is_dir() and d.name.isdigit()]
        job_folders.sort(key=lambda x: x.name)
    
    return {
        "current_job_id": current_id,
        "next_job_id": next_id,
        "total_jobs": len(job_folders),
        "job_folders": [f.name for f in job_folders],
        "latest_job": job_folders[-1].name if job_folders else None,
        "output_directory": str(output_path)
    }
