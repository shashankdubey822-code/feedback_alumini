---
name: debug_auditor
description: Automated error tracing and full-stack regression prevention using Codebase Graph analysis.
---

# PROTOCOL FOR ZERO-ERROR DEBUGGING

Whenever a bug is reported or an edit is made, the `@qa` agent must execute this debugging sequence:

### 1. Root Cause Graph Isolation
Do not guess why a bug is happening. Trace the error lineage:
- Look at the broken component or function node in the Codebase Review Graph.
- Scan backwards through all data imports, inForge queries, and parent modules to find the exact point where data changes state incorrectly.

### 2. Upstream/Downstream Validation
- If the `@developer` proposes a fix in the event manager or certificate manager, you must trace the connection graph to the Hugging Face frontend. 
- Ensure that modifying a backend return variable does not crash the UI keys or parameters on the frontend.

### 3. Verification
Confirm that the fixed file contains 100% complete logic with no placeholder code, missing hooks, or broken references. If any file fails this code check, rollback the file immediately.