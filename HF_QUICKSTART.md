# 🚀 HF Integration - Quick Start

## What Was Just Installed

✓ **huggingface-hub v1.7.2** - Complete HF API library
✓ **VS Code Tasks** - 7 quick command shortcuts
✓ **hf_helper.py** - Python CLI for HF Space management
✓ **Documentation** - Complete setup & usage guides

## 🎯 How to Use - 3 Ways to Interact

### Way 1: VS Code Tasks (Easiest)
```
Press: Ctrl+Shift+P
Type: Tasks: Run Task
Select one of these tasks:
  • HF: Push to Space         (git push to HF)
  • HF: Check Space Status    (view space info)
  • HF: Login to Hugging Face (authenticate)
  • HF: Validate Credentials  (check logged in)
  • Git: View Recent Commits  (see git log)
  • Git: Check Status         (git status)
  • Git: Commit & Push to HF  (quick push workflow)
```

### Way 2: Python Helper Script
```bash
# In terminal, run:
python hf_helper.py auth      # Check authentication
python hf_helper.py info      # Get Space info
python hf_helper.py files     # List Space files
python hf_helper.py status    # Check git status
python hf_helper.py push      # Push to HF
python hf_helper.py help      # Show help
```

### Way 3: Git CLI (Terminal)
```bash
git push huggingface main      # Push to HF
git status                      # Check status
git log --oneline -10           # View commits
git remote -v                   # Show remotes
```

## 📝 Typical Workflow

```
1. Edit files locally in VS Code
2. Save changes
3. Press Ctrl+Shift+P → Tasks: Run Task → "HF: Push to Space"
4. Or run: python hf_helper.py push
5. HF automatically rebuilds (2-3 minutes)
6. Check your Space: https://huggingface.co/spaces/vrfefavr/Feedback_DashBoard
```

## 🔧 First-Time Setup

### Step 1: Get Your HF Token
1. Go to: https://huggingface.co/settings/tokens
2. Click "New token"
3. Name it (e.g., "VS Code")
4. Select "Read and Write" access
5. Copy the token

### Step 2: Authenticate
**Option A (GUI Task):**
```
Press Ctrl+Shift+P → Tasks: Run Task → "HF: Login to Hugging Face"
Paste your token when prompted
```

**Option B (Direct):**
```bash
huggingface-cli login
# or
python -m huggingface_hub.commands login
```

### Step 3: Verify
```bash
python hf_helper.py auth
# Should show your username
```

## 📁 Project Structure with HF Integration

```
mamta_01/
├── .vscode/
│   ├── tasks.json          ← 7 quick tasks
│   └── settings.json       ← VS Code settings
├── .env.example            ← HF config template
├── hf_helper.py            ← Python HF CLI
├── HF_INTEGRATION.md       ← Full documentation (READ THIS!)
├── data/
│   ├── uploads/            ← CSV uploads
│   ├── backups/            ← DB backups
│   └── exports/            ← Reports
├── app.py                  ← Flask backend
├── backend/                ← API logic
├── frontend/               ← HTML/CSS/JS
└── database/               ← SQLite DB
```

## 🎓 Documentation Files

- **HF_INTEGRATION.md** - Complete integration guide
- **.env.example** - Environment variables reference
- **WORKFLOW.md** - Project architecture
- **README.md** - Project overview

## 🔗 Key Links

| Link | Purpose |
|------|---------|
| https://huggingface.co/spaces/vrfefavr/Feedback_DashBoard | Your HF Space |
| https://huggingface.co/settings/tokens | Get API tokens |
| https://huggingface.co/docs | HF Documentation |
| https://huggingface.co/docs/huggingface_hub/guides/cli | HF CLI Guide |

## ✅ Checklist - You're All Set!

- [x] huggingface-hub installed
- [x] VS Code tasks configured
- [x] hf_helper.py script ready
- [x] Complete documentation included
- [x] .env.example updated with HF config
- [ ] **TODO: Set your HF token** (run: `python hf_helper.py auth`)
- [ ] **TODO: First push** (run: `git push huggingface main`)

## 💡 Tips & Tricks

1. **Keyboard Shortcut**: Create a custom keybinding for "HF: Push to Space"
2. **Auto-commit**: Use VS Code's Source Control to commit easily
3. **Monitor Builds**: Check your Space URL for build status
4. **Clean Data**: Periodically clear old files in `data/` folders
5. **Test Locally**: `python app.py` before pushing

## 🆘 Troubleshooting

**Q: "huggingface-cli command not found"**
A: Use Python module instead: `python -c "import huggingface_hub; print(huggingface_hub.__version__)"`

**Q: "Tasks not showing up"**
A: Reload VS Code (Ctrl+Shift+P → Developer: Reload Window)

**Q: "Can't authenticate"**
A: Check your token at https://huggingface.co/settings/tokens

**Q: "Git push fails"**
A: Make sure you're on main branch: `git checkout main`

---

## 🎉 You're Ready!

Everything is set up. Just:
1. Authenticate once: `python hf_helper.py auth`
2. Start developing
3. Push whenever ready: `python hf_helper.py push` or use VS Code tasks

**Questions?** Read **HF_INTEGRATION.md** for detailed docs.

---

**Setup Date**: 2026-03-20
**HF Account**: vrfefavr
**Space**: Feedback_DashBoard
**Status**: ✓ Ready to Deploy
