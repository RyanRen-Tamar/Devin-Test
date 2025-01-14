"""Configuration file for the LAMTA Ad Performance Monitoring project."""

from langchain_openai import ChatOpenAI

# Initialize the LLM with specific model
llm = ChatOpenAI(
    model="chatgpt-4o-latest",
    temperature=0.1  # Lower temperature for more deterministic outputs
)
