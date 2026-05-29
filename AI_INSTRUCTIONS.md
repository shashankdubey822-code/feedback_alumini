# AI Agent Permanent Instructions

**CRITICAL RULES FOR THE AI AGENT TO FOLLOW:**

1. **MASTER CONTEXT:** Before making architectural decisions or trying to understand the project structure, YOU MUST READ the `AI_CONTEXT.md` file located at the root of the project. It contains the ultimate tech stack, database schemas, and critical workflows.
2. **Hugging Face Environment:** The user is working EXCLUSIVELY on Hugging Face Spaces for deployment. Do not assume local development is the primary target. Do not try to run `pip install` or download massive requirements locally unless specifically asked to debug something locally. Keep in mind that changes must be pushed to Hugging Face to take effect.
3. **Model Fallback Transparency:** When switching from the primary AI model to a fallback model (e.g., from Groq to Gemini because of a timeout), explicitly acknowledge this switch in the chat response to the user so they know *why* the response might feel different or why a fallback occurred.
4. **Agentic Data, No Hardcoding:** Do not hardcode questions or suggestions with static string templates (like "What did you think of [Speaker]?"). The AI must dynamically act as an analyst and *generate* its own questions and insights by reading the actual database context. Let the LLM do the heavy lifting.
