#!/usr/bin/env python3
"""
Prepare for commit and push to the repository.
Creates a .gitignore file if needed and generates commit message.
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

def run_command(command):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            universal_newlines=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}")
        print(f"Error details: {e.stderr}")
        return None

def create_gitignore():
    """Create .gitignore file if it doesn't exist or update it"""
    gitignore_path = Path(".gitignore")
    
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# IDE files
.vscode/
.idea/
*.swp
*.swo

# OS specific files
.DS_Store
Thumbs.db

# Project specific
.env
logs/
screenshots/
archive/
confirmations/
data/

# Keep placeholder files
!logs/.gitkeep
!screenshots/.gitkeep
!confirmations/.gitkeep
!data/.gitkeep
"""
    
    if not gitignore_path.exists():
        print("Creating .gitignore file...")
        with open(gitignore_path, 'w') as f:
            f.write(gitignore_content)
        print(".gitignore created.")
    else:
        print(".gitignore already exists.")
        
        # Check if we need to update it
        with open(gitignore_path, 'r') as f:
            current_content = f.read()
        
        # Add any missing entries
        missing_entries = []
        for line in gitignore_content.splitlines():
            if line and not line.startswith('#') and line not in current_content:
                missing_entries.append(line)
        
        if missing_entries:
            print("Updating .gitignore with missing entries:")
            for entry in missing_entries:
                print(f"  - {entry}")
            
            with open(gitignore_path, 'a') as f:
                f.write("\n# Added entries\n")
                for entry in missing_entries:
                    f.write(f"{entry}\n")
            print(".gitignore updated.")

def create_placeholder_files():
    """Create placeholder .gitkeep files in empty directories to preserve them in Git"""
    for directory in ['logs', 'screenshots', 'confirmations', 'data', 'archive']:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {directory}")
        
        gitkeep_path = dir_path / '.gitkeep'
        if not gitkeep_path.exists():
            with open(gitkeep_path, 'w') as f:
                f.write(f"# This file ensures the {directory} directory is tracked by Git\n")
            print(f"Created placeholder: {directory}/.gitkeep")
    
    # Also ensure we have a minimal src structure
    src_dirs = ['src', 'src/utils', 'src/core', 'src/integrations']
    for directory in src_dirs:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {directory}")
            
        # Add __init__.py files
        init_path = dir_path / '__init__.py'
        if not init_path.exists():
            with open(init_path, 'w') as f:
                f.write(f'"""\n{directory.split("/")[-1]} module for Competition Auto-Entry System\n"""\n')
            print(f"Created __init__.py: {init_path}")

def generate_commit_message():
    """Generate a commit message based on the changes"""
    # Get current date and time
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    
    # Check if there are any MCP/CV files
    mcp_files = run_command('git ls-files *mcp* *cv* competition_auto_entry*.py enhanced*.py')
    
    if mcp_files:
        message = f"Refactor: Convert to MCP/CV-based competition entry system ({date_str})"
    else:
        message = f"Cleanup: Remove legacy code and prepare for new MCP/CV system ({date_str})"
    
    # Add details
    message += "\n\n"
    message += "This commit:\n"
    message += "- Removes legacy Selenium-based scraper code\n"
    message += "- Retains only essential files for the new MCP/CV system\n"
    message += "- Updates requirements to only include actually used packages\n"
    message += "- Reorganizes project structure for better maintainability\n"
    message += "- Improves cross-platform compatibility (Windows, Linux, macOS)\n"
    
    return message

def check_git_status():
    """Check git status and show changes"""
    print("\nChecking git status...")
    status = run_command('git status')
    print(status)
    
    # Check if there are changes
    if "nothing to commit" in status:
        print("No changes to commit.")
        return False
    
    return True

def prepare_for_commit():
    """Prepare the repository for commit"""
    # Create/update .gitignore
    create_gitignore()
    
    # Create placeholder files
    create_placeholder_files()
    
    # Check git status
    has_changes = check_git_status()
    if not has_changes:
        return
    
    # Generate commit message
    commit_message = generate_commit_message()
    
    print("\nSuggested commit message:")
    print("-" * 80)
    print(commit_message)
    print("-" * 80)
    
    # Ask for confirmation
    confirmation = input("\nDo you want to add all changes and commit with this message? (y/n): ")
    if confirmation.lower() != 'y':
        print("Commit cancelled.")
        return
    
    # Add all changes
    print("\nAdding all changes...")
    run_command('git add .')
    
    # Commit
    print("Committing changes...")
    commit_result = run_command(f'git commit -m "{commit_message}"')
    print(commit_result)
    
    # Ask about pushing
    push_confirmation = input("\nDo you want to push the changes to the remote repository? (y/n): ")
    if push_confirmation.lower() == 'y':
        print("Pushing changes...")
        push_result = run_command('git push')
        print(push_result)
    else:
        print("Push cancelled. You can push later with 'git push'.")

if __name__ == "__main__":
    # Change to the repository root directory
    repo_root = Path(__file__).parent.absolute()
    os.chdir(repo_root)
    print(f"Working in repository: {repo_root}")
    
    prepare_for_commit()
