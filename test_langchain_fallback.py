import os
import time
import asyncio
from typing import Any, Dict, List
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mistralai import ChatMistralAI
from langchain_cohere import ChatCohere

# Load environment variables
load_dotenv()

# ==============================================================================
# MODEL INITIALIZATION
# ==============================================================================
# We initialize all our free models here. We add short timeouts to ensure fast
# failure if the API is down or the model endpoint is invalid.

def get_models():
    """Initializes all available models with strict timeout rules."""
    
    # 1. OpenRouter (Primary Llama 3.3 70B)
    openrouter = ChatOpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY", "dummy"),
        base_url="https://openrouter.ai/api/v1",
        model="meta-llama/llama-3.3-70b-instruct:free",
        max_retries=0, # Fail fast
        request_timeout=5.0
    )
    
    # 2. Groq (Backup Llama 3.3 70B)
    groq = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY", "dummy"),
        model="llama-3.3-70b-versatile",
        max_retries=0,
        request_timeout=5.0
    )
    
    # 3. Gemini (Flash 2.5)
    gemini = ChatGoogleGenerativeAI(
        google_api_key=os.getenv("GEMINI_API_KEY", "dummy"),
        model="gemini-2.5-flash",
        max_retries=0,
        request_timeout=5.0
    )
    
    # 4. Cohere (Command R)
    cohere = ChatCohere(
        cohere_api_key=os.getenv("COHERE_API_KEY", "dummy"),
        model="command-r",
        max_retries=0,
        request_timeout=5.0
    )
    
    # 5. Mistral (Nemo)
    mistral = ChatMistralAI(
        mistral_api_key=os.getenv("MISTRAL_API_KEY", "dummy"),
        model="open-mistral-nemo",
        max_retries=0,
        timeout=5.0
    )
    
    return [openrouter, groq, gemini, cohere, mistral]


# ==============================================================================
# STRATEGY 1: INSTANTANEOUS FALLBACK CHAIN (LangChain .with_fallbacks)
# ==============================================================================
# This strategy tries the first model. If it fails, it drops down to the next
# model in less than 2 milliseconds automatically.

def test_fallback_chain():
    print("--- Testing Strategy 1: Instant Fallback Chain ---")
    models = get_models()
    
    # To test the <2ms fallback, we artificially break the first model
    broken_openrouter = ChatOpenAI(
        api_key="INVALID_KEY_TO_FORCE_ERROR",
        base_url="https://openrouter.ai/api/v1",
        model="meta-llama/llama-3.3-70b-instruct:free",
        max_retries=0
    )
    
    # Construct the fallback chain:
    # Primary: broken_openrouter
    # Fallbacks: groq, gemini, cohere, mistral
    fallback_llm = broken_openrouter.with_fallbacks(models[1:])
    
    prompt = ChatPromptTemplate.from_template("Tell me a quick 1-sentence joke about AI.")
    chain = prompt | fallback_llm
    
    start_time = time.time()
    try:
        # The primary will fail immediately, and LangChain will instantly 
        # route to the groq model.
        result = chain.invoke({})
        end_time = time.time()
        print(f"Result: {result.content}")
        print(f"Time Taken (including fallback): {end_time - start_time:.2f} seconds")
    except Exception as e:
        print(f"All models failed! Error: {e}")


# ==============================================================================
# STRATEGY 2: PARALLEL RACING (LangChain / asyncio)
# ==============================================================================
# This strategy fires all models at the EXACT SAME TIME and returns the result
# from whichever model finishes first. The others are cancelled.

async def race_models_async():
    print("\n--- Testing Strategy 2: Parallel Racing ---")
    models = get_models()
    prompt = ChatPromptTemplate.from_template("Tell me a quick 1-sentence joke about space.")
    
    # Create independent chains for each model
    chains = [prompt | model for model in models]
    
    start_time = time.time()
    
    # Execute all models in parallel using asyncio.as_completed
    # This acts as our "LangGraph parallel node" behavior natively.
    tasks = [asyncio.create_task(chain.ainvoke({})) for chain in chains]
    
    first_result = None
    for coro in asyncio.as_completed(tasks):
        try:
            first_result = await coro
            # We got our first successful response, cancel the others
            for task in tasks:
                if not task.done():
                    task.cancel()
            break
        except Exception as e:
            # This model failed, but we just let the others keep racing
            print(f"[Warning] A model failed during race: {e}")
            continue
            
    end_time = time.time()
    
    if first_result:
        print(f"First Result Received: {first_result.content}")
        print(f"Race Time: {end_time - start_time:.2f} seconds")
    else:
        print("All models failed the race.")


if __name__ == "__main__":
    # Test 1: Fallback logic (Synchronous)
    test_fallback_chain()
    
    # Test 2: Parallel Racing (Asynchronous)
    asyncio.run(race_models_async())
