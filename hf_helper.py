#!/usr/bin/env python3
"""
Hugging Face Integration Helper Script
Quick commands to manage your HF Space from VS Code terminal
"""

import sys
import subprocess
import os
from pathlib import Path

# Force UTF-8 encoding on Windows
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    from huggingface_hub import whoami, list_repo_files, model_info
except ImportError:
    print("ERROR: huggingface_hub not installed. Run: pip install huggingface-hub")
    sys.exit(1)

HF_SPACE_ID = "vrfefavr/Feedback_DashBoard"
HF_SPACE_URL = f"https://huggingface.co/spaces/{HF_SPACE_ID}"

def clean_text(text):
    """Remove problematic unicode characters for Windows compatibility"""
    replacements = {
        '✓': '[OK]', '✗': '[FAIL]', '📁': '[FILES]', 'ℹ': '[INFO]',
        '🚀': '[PUSH]', '📊': '[STATUS]', '🎯': '', '⚡': '[FAST]',
        '💾': '[SAVE]', '🔐': '[SECURE]', '📢': '[INFO]'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def print_banner(msg):
    """Print formatted banner with safe text"""
    msg_clean = clean_text(msg)
    print(f"\n{'='*60}")
    print(f"  {msg_clean}")
    print(f"{'='*60}\n")

def print_section(title):
    """Print section header"""
    title_clean = clean_text(title)
    print(f"\n>> {title_clean}")

def safe_print(text):
    """Safely print text with encoding handling"""
    text_clean = clean_text(str(text))
    try:
        print(text_clean)
    except UnicodeEncodeError:
        print(text_clean.encode('ascii', errors='replace').decode('ascii'))

def check_auth():
    """Check if user is authenticated with HF"""
    print_banner("[OK] HF Authentication Status")
    try:
        user = whoami()
        safe_print(f"Logged in as: {user['name']}")
        orgs = user.get('orgs', [])
        org_str = ', '.join(orgs) if orgs else '(none)'
        safe_print(f"Orgs: {org_str}")
        safe_print("\n[OK] Authentication successful!")
        return True
    except Exception as e:
        print_banner("[FAIL] Not Authenticated")
        safe_print(f"Error: {str(e)}")
        safe_print("\nTo login, run: python -m huggingface_hub.commands.login")
        return False

def list_space_files():
    """List files in your HF Space"""
    print_banner("[FILES] HF Space Files")
    try:
        files = list_repo_files(HF_SPACE_ID, repo_type="space")
        for f in sorted(files)[:20]:
            safe_print(f"  {f}")
        if len(files) > 20:
            safe_print(f"\n  ... and {len(files) - 20} more files")
        safe_print(f"\nTotal files: {len(files)}")
    except Exception as e:
        safe_print(f"Error: {str(e)}")
        safe_print("Are you authenticated? Run: python hf_helper.py auth")

def get_space_info():
    """Get Space metadata"""
    print_banner("[INFO] HF Space Information")
    try:
        info = model_info(HF_SPACE_ID, repo_type="space")
        safe_print(f"ID: {info.id}")
        safe_print(f"URL: {HF_SPACE_URL}")
        safe_print(f"Private: {info.private}")
        safe_print(f"Created: {info.created_at}")
        safe_print(f"Last Modified: {info.last_modified}")
    except Exception as e:
        safe_print(f"Error: {str(e)}")

def quick_push():
    """Quick push to HF with one command"""
    print_banner("[PUSH] Pushing to HF Space")
    try:
        result = subprocess.run(
            ["git", "push", "huggingface", "main"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        if result.stdout:
            safe_print(result.stdout)
        if result.stderr and "warning" not in result.stderr.lower():
            safe_print(result.stderr)
        if result.returncode == 0:
            safe_print("\n[OK] Push successful! HF will rebuild in 2-3 minutes.")
        else:
            safe_print("\n[FAIL] Push failed!")
            if result.stderr:
                safe_print(f"Details: {result.stderr}")
            return False
        return True
    except Exception as e:
        safe_print(f"Error: {str(e)}")
        return False

def git_status():
    """Show git status"""
    print_banner("[STATUS] Git Status")
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        if result.stdout:
            safe_print(result.stdout)
        else:
            safe_print("[OK] Everything is committed!")
    except Exception as e:
        safe_print(f"Error: {str(e)}")

def show_help():
    """Show available commands"""
    print_banner("HF Space CLI Commands")
    help_text = """
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
  python hf_helper.py status
  python hf_helper.py files

First time setup:
  1. python hf_helper.py auth
  2. (Authenticate when prompted)
  3. python hf_helper.py push

Space URL: https://huggingface.co/spaces/vrfefavr/Feedback_DashBoard
    """
    safe_print(help_text)

def main():
    """Main entry point"""
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
        try:
            commands[cmd]()
        except Exception as e:
            safe_print(f"\n[FAIL] Unexpected error: {str(e)}")
            safe_print("Run with --help for usage information")
    else:
        safe_print(f"Unknown command: {cmd}")
        show_help()

if __name__ == "__main__":
    main()
