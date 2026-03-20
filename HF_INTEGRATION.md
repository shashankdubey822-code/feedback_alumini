# 🚀 Hugging Face Integration Guide

This guide shows you how to use the Hugging Face CLI and VS Code integration for seamless development with your HF Space.

## 📋 Quick Setup

### 1. Login to Hugging Face

```bash
huggingface-cli login
```

When prompted, paste your **HF API token** (get it from https://huggingface.co/settings/tokens)

### 2. Verify Authentication

```bash
huggingface-cli whoami
```

You should see your username and organizations.

## 🛠️ Available Commands

### Via VS Code Tasks (Press `Ctrl+Shift+P`)

Type **"Tasks: Run Task"** and select:

| Task | What It Does |
|------|-------------|
| **HF: Push to Space** | Git push to Hugging Face |
| **HF: Check Space Status** | View your Space info |
| **HF: Login to Hugging Face** | Authenticate with HF |
| **HF: Validate Credentials** | Verify you're logged in |
| **Git: View Recent Commits** | Show last 10 commits |
| **Git: Check Status** | Show git status |

### Via Python Helper Script

```bash
# Check authentication status
python hf_helper.py auth

# Get Space information
python hf_helper.py info

# List files in your Space
python hf_helper.py files

# Check git status
python hf_helper.py status

# Push to HF Space
python hf_helper.py push

# Show help
python hf_helper.py help
```

### Via Command Line

```bash
# Push to HF
git push huggingface main

# Check remotes
git remote -v

# View logs
git log --oneline -10

# Check status
git status
```

## 🌐 Your HF Space

- **Space URL**: https://huggingface.co/spaces/vrfefavr/Feedback_DashBoard
- **Space ID**: `vrfefavr/Feedback_DashBoard`
- **Git Remote**: `huggingface` (configured)

## 📁 Data Directories

All your data persists in the HF Space:

```
data/
├── uploads/     # Uploaded CSV files
├── backups/     # Database backups
└── exports/     # Generated reports
```

## 🔄 Typical Workflow

### 1. Make Changes Locally
Edit files in VS Code as normal

### 2. Commit Changes
```bash
git add .
git commit -m "Your commit message"
```

Or use git UI in VS Code

### 3. Push to HF Space
**Option A:** Use VS Code Task
- Press `Ctrl+Shift+P`
- Type "Tasks: Run Task"
- Select "HF: Push to Space"

**Option B:** Use terminal
```bash
git push huggingface main
```

**Option C:** Use helper script
```bash
python hf_helper.py push
```

### 4. Monitor Deployment
HF will automatically rebuild your Space (takes 2-3 minutes)

## 🔑 Token Management

Your HF token is stored securely in:
- **Windows**: `%USERPROFILE%\.huggingface\token`
- **Mac/Linux**: `~/.huggingface/token`

**Never commit your `.env` file with tokens!** It's already in `.gitignore`.

## 🐛 Troubleshooting

### "Not authenticated"
```bash
huggingface-cli login
# Then paste your token from https://huggingface.co/settings/tokens
```

### "Push rejected"
```bash
# Make sure you're on main branch
git branch

# If not on main, switch:
git checkout main

# Then push
git push huggingface main
```

### "Task not found"
- Reload VS Code: `Ctrl+Shift+P` → "Developer: Reload Window"
- Make sure `.vscode/tasks.json` exists

## 📚 Useful Links

- **HF Documentation**: https://huggingface.co/docs
- **HF CLI Guide**: https://huggingface.co/docs/huggingface_hub/guides/cli
- **Your Space**: https://huggingface.co/spaces/vrfefavr/Feedback_DashBoard
- **HF Tokens**: https://huggingface.co/settings/tokens

## 💡 Tips

1. **Check Space status regularly**: `python hf_helper.py info`
2. **Always commit before pushing**: Avoid loose ends
3. **Use meaningful commit messages**: For tracking changes
4. **Monitor build logs**: HF shows deployment status
5. **Keep data folders clean**: Remove old uploads/backups periodically

---

**Last Updated**: 2026-03-20
**HF Account**: vrfefavr
**Space**: Feedback_DashBoard
