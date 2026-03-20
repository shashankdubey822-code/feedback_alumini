#!/usr/bin/env python3
"""
Hugging Face Integration Helper Script
Quick commands to manage your HF Space from VS Code terminal
"""

import sys
import subprocess
from huggingface_hub import whoami, list_repo_files, model_info
from pathlib import Path

HF_SPACE_ID = "vrfefavr/Feedback_DashBoard"
HF_SPACE_URL = f"https://huggingface.co/spaces/{HF_SPACE_ID}"

def print_banner(msg):
    # Remove emoji for Windows terminal compatibility
    msg_clean = msg.replace('✓', '[OK]').replace('✗', '[FAIL]').replace('📁', '[FILES]').replace('ℹ️', '[INFO]').replace('🚀', '[PUSH]').replace('📊', '[STATUS]').replace('🎯', '')
    print(f"\n{'='*60}")
    print(f"  {msg_clean}")
    print(f"{'='*60}\n")

def check_auth():
    """Check if user is authenticated with HF"""
    try:
        user = whoami()
        print_banner("✓ HF Authentication Status")
        print(f"Logged in as: {user['name']}")
        print(f"Orgs: {', '.join(user.get('orgs', ['(none)']))}")
        return True
    except Exception as e:
        print_banner("✗ Not Authenticated")
        print(f"Error: {str(e)}")
        print("\nTo login, run: huggingface-cli login")
        return False

def list_space_files():
    """List files in your HF Space"""
    try:
        print_banner("📁 HF Space Files")
        files = list_repo_files(HF_SPACE_ID, repo_type="space")
        for f in sorted(files)[:20]:  # Show first 20
            print(f"  {f}")
        if len(files) > 20:
            print(f"\n  ... and {len(files) - 20} more files")
        print(f"\nTotal files: {len(files)}")
    except Exception as e:
        print(f"Error: {str(e)}")

def get_space_info():
    """Get Space metadata"""
    try:
        print_banner("ℹ️  HF Space Information")
        info = model_info(HF_SPACE_ID, repo_type="space")
        print(f"ID: {info.id}")
        print(f"URL: {HF_SPACE_URL}")
        print(f"Private: {info.private}")
        print(f"Created: {info.created_at}")
        print(f"Last Modified: {info.last_modified}")
    except Exception as e:
        print(f"Error: {str(e)}")

def quick_push():
    """Quick push to HF with one command"""
    print_banner("🚀 Pushing to HF Space")
    try:
        result = subprocess.run(
            ["git", "push", "huggingface", "main"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        if result.returncode == 0:
            print("✓ Push successful!")
        else:
            print("✗ Push failed!")
            return False
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

def git_status():
    """Show git status"""
    print_banner("📊 Git Status")
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        if result.stdout:
            print(result.stdout)
        else:
            print("✓ Everything is committed!")
    except Exception as e:
        print(f"Error: {str(e)}")

def show_help():
    """Show available commands"""
    print_banner("🎯 HF Space CLI Commands")
    print("""
Usage: python hf_helper.py <command>

Commands:
  auth       - Check HF authentication status
  info       - Get Space information
  files      - List Space files
  status     - Show git status
  push       - Push to HF Space
  help       - Show this help

Examples:
  python hf_helper.py auth
  python hf_helper.py push
  python hf_helper.py info
    """)

def main():
    if len(sys.argv) < 2:
        show_help()
        return

    cmd = sys.argv[1].lower()

    commands = {
        "auth": check_auth,
        "info": get_space_info,
        "files": list_space_files,
        "status": git_status,
        "push": quick_push,
        "help": show_help,
        "-h": show_help,
        "--help": show_help,
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"Unknown command: {cmd}")
        show_help()

if __name__ == "__main__":
    main()
