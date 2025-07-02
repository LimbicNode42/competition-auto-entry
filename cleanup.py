#!/usr/bin/env python3
"""
Cleanup script for the Competition Auto-Entry System.
Removes files that are not needed in the new MCP/CV-based system.
"""

import os
import shutil
import argparse
from pathlib import Path

# Files essential to the new MCP/CV system that should NOT be removed
ESSENTIAL_FILES = [
    # Core system files - keep these at the root level
    "./competition_auto_entry.py",
    "./competition_auto_entry_final.py",
    "./enhanced_competition_entry.py",
    "./enhanced_mcp_entry_system.py",
    "./setup_mcp_servers.py",
    "./direct_entry_test.py",
    "./cleanup.py",
    "./prepare_commit.py",
    
    # Test files
    "./test_cv_competition_entry.py",
    "./test_form.html",
    "./test_live_competition.py",
    "./test_public_competition.py",
    "./test_final_competition.py",
    
    # Summary reports
    "./summary_report.py",
    "./README-final.md",
    
    # Configuration files
    "./requirements-mcp-working.txt",
    "./requirements-mcp.txt",
    "./.env",
    "./.env.example",
    "./.gitignore",
    "./README.md",
]

# Files to archive in the legacy system
ARCHIVE_FILES = [
    "./main.py",
    "./check_entry_stats.py",
    "./view_confirmations.py",
    "./check_readiness.py",
    "./requirements.txt",
    "./setup.py",
    "./setup_personal_config.py",
    "./test_all_aggregators.py",
    "./test_entry_process.py",
    "./review_rejections.py",
    "./example.py",
    "src/core/scraper.py",
    "src/core/modular_scraper.py",
    "src/integrations/google_auth.py",
    "src/integrations/basic_auth.py",
    "src/integrations/aggregators.py",
    "src/utils/entry_confirmation.py",
    "src/utils/rejection_logger.py",
]

def cleanup_workspace(dry_run=True, archive=True):
    """
    Clean up the workspace by removing files not needed in the new system.
    
    Args:
        dry_run: If True, only print actions without actually deleting files
        archive: If True, move files to an archive folder instead of deleting
    """
    root_dir = Path(__file__).parent.absolute()
    print(f"Cleaning up workspace at: {root_dir}")
    
    # Create archive directory if needed
    archive_dir = root_dir / "archive"
    if archive and not dry_run:
        archive_dir.mkdir(exist_ok=True)
        print(f"Created archive directory at: {archive_dir}")
    
    # Get all files in the workspace
    all_files = []
    for root, dirs, files in os.walk(root_dir):
        # Skip directories we don't want to touch
        if any(skip in root for skip in [".git", "venv", "__pycache__", "archive", "screenshots", "logs", "config"]):
            continue
        
        # Convert to relative path
        rel_root = os.path.relpath(root, root_dir)
        rel_root = "" if rel_root == "." else rel_root
        
        for file in files:
            if rel_root:
                rel_path = os.path.join(rel_root, file).replace("\\", "/")
            else:
                rel_path = f"./{file}"
            all_files.append(rel_path)
    
    # Identify files to keep, archive, and remove
    files_to_keep = []
    files_to_archive = []
    files_to_remove = []
    
    for file in all_files:
        # Check if file is in essential files
        if file in ESSENTIAL_FILES:
            files_to_keep.append(file)
        # Check if file is to be archived
        elif any(file == archive_file or file.startswith(archive_file) for archive_file in ARCHIVE_FILES):
            files_to_archive.append(file)
        # Otherwise, mark for removal
        else:
            files_to_remove.append(file)
    
    # Print summary
    print(f"\nTotal files analyzed: {len(all_files)}")
    print(f"Files to keep: {len(files_to_keep)}")
    print(f"Files to archive: {len(files_to_archive)}")
    print(f"Files to remove: {len(files_to_remove)}")
    
    # Print lists of files
    print("\nFiles to keep:")
    for file in sorted(files_to_keep):
        print(f"  - {file}")
    
    print("\nFiles to archive:")
    for file in sorted(files_to_archive):
        print(f"  - {file}")
    
    print("\nFiles to remove:")
    for file in sorted(files_to_remove):
        print(f"  - {file}")
    
    # Confirm before proceeding
    if not dry_run:
        confirmation = input("\nProceed with cleanup? (y/n): ")
        if confirmation.lower() != 'y':
            print("Cleanup cancelled.")
            return
        
        # Perform archive operation
        if archive and files_to_archive:
            for file in files_to_archive:
                src_path = root_dir / file.lstrip("./")
                dst_path = archive_dir / file.lstrip("./")
                dst_dir = dst_path.parent
                dst_dir.mkdir(parents=True, exist_ok=True)
                print(f"Archiving: {file}")
                shutil.copy2(src_path, dst_path)
                
                # Remove the original
                os.remove(src_path)
        
        # Perform remove operation
        for file in files_to_remove:
            file_path = root_dir / file.lstrip("./")
            print(f"Removing: {file}")
            if file_path.is_file():
                os.remove(file_path)
        
        print("\nCleanup completed!")
    else:
        print("\nDry run completed. No files were modified.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up the Competition Auto-Entry workspace")
    parser.add_argument("--execute", action="store_true", help="Execute the cleanup (default is dry run)")
    parser.add_argument("--no-archive", action="store_true", help="Delete files instead of archiving them")
    
    args = parser.parse_args()
    
    cleanup_workspace(
        dry_run=not args.execute,
        archive=not args.no_archive
    )
