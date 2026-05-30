---
trigger: always_on
---

## GRAPH-BASED INTEGRITY RULE
- The agent is strictly forbidden from executing file mutations without invoking a programmatic abstract syntax tree (AST) code-graph traversal first.
- The agent must proactively declare any breaking changes to downstream inForge queries or Hugging Face schema endpoints *prior* to file execution.

---
name: Cloud-Isolated Deployment Rules
description: Hard-blocks the agent from executing local code files, running scripts, or installing package requirements due to an isolated cloud runtime environment.
---

# CRITICAL OPERATIONAL SECURITY MANDATES

This project is a cloud-only implementation. The backend runs exclusively on inForge, and the frontend runs exclusively on Hugging Face Spaces. The local machine does not possess the matching system libraries.

### 1. ABSOLUTE TERMINAL COMMAND BAN
- You are STRICTLY FORBIDDEN from running `python`, `node`, `npm run`, or executing any local server binaries. 
- DO NOT execute environment setup tools, compilation commands, or local execution blocks.
- DO NOT run `pip install`, `pip install -r requirements.txt`, or modify system variables. If a package is missing, simply write it to the config file as static text, but NEVER run the installer.

### 2. CODE-ONLY MANIPULATION PROTOCOL
- Treat this workspace strictly as a cold text repository. You are here to write code, patch logic bugs, update database queries, and structure frontend components. 
- You must write code defensively, ensuring everything matches the target inForge and Hugging Face specifications without testing it on the local processor.

### 3. NO EXECUTION RECOVERY LOOPS
- If a script or layout file fails, do not try to boot it up locally to figure out why. Use your **Codebase Review Graph** tool to statically trace the syntax and fix the file errors purely through code logic analysis.
