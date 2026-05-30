import os
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

def test_fallback():
    # Use invalid groq key to force fallback
    groq = ChatGroq(api_key="invalid_key", model="llama-3.3-70b-versatile", max_retries=0)
    
    gemini_key = os.environ.get("GEMINI_API_KEY")
    gemini = ChatGoogleGenerativeAI(google_api_key=gemini_key, model="gemini-2.5-flash")
    
    chain = groq.with_fallbacks([gemini])
    
    try:
        res = chain.invoke([HumanMessage(content="Hello")])
        print("Response metadata:", res.response_metadata)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_fallback()
