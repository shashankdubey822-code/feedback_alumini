# Free LLM Providers Guide (as of 2025)

This document summarizes known free or freemium LLM providers, example free model IDs, how to obtain API keys, and the recommended environment variable names to store keys. This is a research-style snapshot — always verify provider docs for the latest model IDs, rate limits and terms.

Providers covered below:

- OpenRouter
- Groq
- Hugging Face Inference API
- Google Gemini
- TogetherAI
- Mistral AI
- Cohere
- Cloudflare Workers AI

---

## A. OpenRouter (https://openrouter.ai)

- Representative free model IDs (those ending with `:free`):
  - `google/gemini-flash-1.5-8b:free`
  - `meta-llama/llama-3.3-70b-instruct:free`
  - `mistralai/mistral-7b-instruct:free`
  - `deepseek/deepseek-r1:free`
- Typical limits: provider-specific; some `:free` models are permanently free but may have rate limits or usage quotas. Verify on the OpenRouter dashboard.
- Free vs trial: Many `:free` model IDs on OpenRouter are flagged as permanently-available free tiers (no credit card required) — confirm on the model details page.
- How to get an API key:
  1. Visit: https://openrouter.ai
  2. Sign up / log in
  3. Go to Settings → API Keys (https://openrouter.ai/settings/keys)
  4. Create a new key and copy it.
- Env variable to use: `OPENROUTER_API_KEY`

---

## B. Groq (https://console.groq.com)

- Example models often advertised for free-tier experimentation (examples; check Groq console for exact availability):
  - `llama3-70b-8192`
  - `llama-3.3-70b-versatile`
  - `mixtral-8x7b-32768`
  - `gemma2-9b-it`
- Rate limits: model-dependent and subject to the account tier — consult the Groq console for per-model throttling and quotas.
- API key location: https://console.groq.com/keys
- Env variable to use: `GROQ_API_KEY`

---

## C. Hugging Face Inference API (https://huggingface.co)

- Example free/hosted model examples (availability varies by model license and hosting):
  - `meta-llama/Llama-3.1-8B-Instruct`
  - `mistralai/Mistral-7B-Instruct-v0.3`
- Free tier: Hugging Face provides a free tier token for inference with rate limits; no credit card required for basic usage.
- How to get an API key: https://huggingface.co/settings/tokens → New token → choose `read` scope for inference
- Endpoint pattern: `https://api-inference.huggingface.co/models/{model_id}`
- Env variable to use: `HUGGINGFACE_API_KEY`

---

## D. Google Gemini (AI Studio / Vertex-like endpoints)

- Representative model names that may appear in provider docs or partner integrations:
  - `gemini-1.5-flash`
  - `gemini-1.5-flash-8b`
  - `gemini-2.0-flash-exp`
- Free tier: Google provides limited free-tier usage or credits in some developer programs; check Google AI Studio quotas.
- API key / access: https://aistudio.google.com (follow Google Cloud / AI Studio instructions)
- Env variable to use (suggested): `GEMINI_API_KEY`

---

## E. Together AI (https://api.together.xyz)

- Notes: Together hosts a variety of community/open models and may provide small free credits on signup.
- Example items: `meta-llama/Llama-3.3-70B-Instruct-Turbo` (availability varies)
- API key location: https://api.together.xyz/settings/api-keys
- Env variable to use: `TOGETHER_API_KEY`

---

## F. Mistral AI (https://console.mistral.ai)

- Example free-tier or community models:
  - `mistral-small-latest`
  - `open-mistral-7b`
- API key: https://console.mistral.ai/api-keys
- Env variable to use: `MISTRAL_API_KEY`

---

## G. Cohere (https://dashboard.cohere.com)

- Example models (Cohere frequently names models like `command-*`):
  - `command-r`
  - `command-light`
- Free trial / tier: Cohere provides a free trial or free usage tier for developer accounts; check dashboard for exact limits.
- API key: https://dashboard.cohere.com/api-keys
- Env variable to use: `COHERE_API_KEY`

---

## H. Cloudflare Workers AI (Cloudflare.ai)

- Example Cloudflare bundle model identifiers used in Workers AI examples:
  - `@cf/meta/llama-3.1-8b-instruct`
  - `@cf/mistral/mistral-7b-instruct-v0.1`
- Access: Cloudflare account (free tier) and Workers AI product; consult Cloudflare dashboard.
- Env variables to use: `CLOUDFLARE_API_KEY` and `CLOUDFLARE_ACCOUNT_ID`

---

## I. Other providers

There are additional regional / specialty providers offering free tiers, research models, or community-hosted models (e.g. smaller self-hosted inference APIs, university-hosted endpoints). Always check provider documentation for precise model IDs, rate limits, and terms.

---

## ⚡ QUICK COPY — ENV VARIABLES

Copy these into your .env file and fill in your keys:

OPENROUTER_API_KEY=
GROQ_API_KEY=
HUGGINGFACE_API_KEY=
GEMINI_API_KEY=
TOGETHER_API_KEY=
MISTRAL_API_KEY=
COHERE_API_KEY=
CLOUDFLARE_API_KEY=
CLOUDFLARE_ACCOUNT_ID=

---

## 🔬 VERIFIED WORKING MODELS (Test Results — May 2026)

The following models successfully connected and returned correct test responses:

### 1. OpenRouter (API Key Configured)
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` (OK)
- `poolside/laguna-xs.2:free` (OK)
- `poolside/laguna-m.1:free` (OK)
- `moonshotai/kimi-k2.6:free` (OK)
- `google/gemma-4-26b-a4b-it:free` (OK)
- `google/gemma-4-31b-it:free` (OK)
- `nvidia/nemotron-3-super-120b-a12b:free` (OK)
- `liquid/lfm-2.5-1.2b-thinking:free` (OK)
- `liquid/lfm-2.5-1.2b-instruct:free` (OK)
- `nvidia/nemotron-3-nano-30b-a3b:free` (OK)
- `nvidia/nemotron-nano-12b-v2-vl:free` (OK)
- `nvidia/nemotron-nano-9b-v2:free` (OK)
- `openai/gpt-oss-120b:free` (OK)
- `openai/gpt-oss-20b:free` (OK)
- `z-ai/glm-4.5-air:free` (OK)

### 2. Groq (API Key Configured)
- `llama-3.3-70b-versatile` (OK)
- `openai/gpt-oss-20b` (OK)
- `openai/gpt-oss-120b` (OK)
- `groq/compound-mini` (OK)
- `groq/compound` (OK)
- `allam-2-7b` (OK)
- `qwen/qwen3-32b` (OK)
- `llama-3.1-8b-instant` (OK)
- `meta-llama/llama-4-scout-17b-16e-instruct` (OK)

### 3. Google Gemini (API Key Configured)
- `models/gemini-2.5-flash` (OK)
- `models/gemma-4-26b-a4b-it` (OK)
- `models/gemma-4-31b-it` (OK)
- `models/gemini-2.5-flash-lite` (OK)
- `models/gemini-3.1-flash-lite` (OK)

### 4. Mistral (API Key Configured)
- `open-mistral-nemo-2407` (OK)
- `mistral-tiny-2407` (OK)
- `mistral-tiny-latest` (OK)
- `devstral-2512` (OK)
- `devstral-medium-latest` (OK)
- `devstral-latest` (OK)
- `mistral-small-2603` (OK)
- `mistral-vibe-cli-fast` (OK)
- `magistral-small-latest` (OK)
- `magistral-medium-2509` (OK)
- `magistral-medium-latest` (OK)
- `voxtral-small-2507` (OK)
- `voxtral-small-latest` (OK)
- `mistral-large-2512` (OK)
- `mistral-large-latest` (OK)
- `ministral-3b-2512` (OK)
- `ministral-3b-latest` (OK)
- `ministral-8b-2512` (OK)
- `ministral-8b-latest` (OK)
- `ministral-14b-2512` (OK)
- `ministral-14b-latest` (OK)
- `mistral-medium-3-5` (OK)
- `mistral-medium-3.5` (OK)
- `mistral-medium-3` (OK)
- `mistral-medium-2604` (OK)
- `mistral-medium-c21211-r0-75` (OK)
- `mistral-vibe-cli-latest` (OK)
- `pixtral-large-2411` (OK)
- `pixtral-large-latest` (OK)
- `mistral-large-pixtral-2411` (OK)
- `devstral-small-2507` (OK)
- `devstral-medium-2507` (OK)
- `voxtral-mini-2507` (OK)
- `voxtral-mini-latest` (OK)
- `magistral-small-2509` (OK)
- `mistral-small-2506` (OK)

### 5. Cohere (API Key Configured)
- `command-r7b-12-2024` (OK)
- `c4ai-aya-expanse-32b` (OK)
- `c4ai-aya-vision-32b` (OK)
- `command-a-03-2025` (OK)
- `command-a-plus-05-2026` (OK)
- `command-a-reasoning-08-2025` (OK)
- `command-a-translate-08-2025` (OK)
- `command-a-vision-07-2025` (OK)
- `command-r-08-2024` (OK)
- `command-r-plus-08-2024` (OK)
- `command-r7b-arabic-02-2025` (OK)

---

## 📝 Notes & Caveats

- Model availability, model IDs and exact free quotas change fast — always verify the provider's official docs before relying on a given model ID.
- Some providers expose OpenAI-compatible endpoints while others require provider-specific request shapes.
- When building automated tests, start with `Hugging Face` and `OpenRouter` or provider SDKs since they're often easiest to call with `requests` directly.
