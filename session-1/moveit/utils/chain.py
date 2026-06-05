"""
LangChain chain factory.
Builds a companion response chain using ChatAnthropic + a system persona.
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
import streamlit as st


def get_llm() -> ChatAnthropic:
    """Return a cached ChatAnthropic LLM instance."""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    return ChatAnthropic(
        model="claude-sonnet-4-5",
        anthropic_api_key=api_key,
        max_tokens=300,
        temperature=0.85,
    )


def build_companion_chain(persona: str):
    """
    Build a simple persona → prompt → LLM → string chain.
    Returns a LangChain Runnable.
    """
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(persona),
        HumanMessagePromptTemplate.from_template("{user_prompt}"),
    ])
    llm = get_llm()
    return prompt | llm | StrOutputParser()


def run_companion(persona: str, user_prompt: str) -> str:
    """
    Synchronously run a companion chain and return the response string.
    Wraps exceptions gracefully.
    """
    try:
        chain = build_companion_chain(persona)
        return chain.invoke({"user_prompt": user_prompt})
    except Exception as e:
        return f"[Connection issue — check your API key. Error: {e}]"


def stream_companion(persona: str, user_prompt: str):
    """
    Generator that streams tokens from the companion chain.
    Use with st.write_stream().
    """
    try:
        chain = build_companion_chain(persona)
        yield from chain.stream({"user_prompt": user_prompt})
    except Exception as e:
        yield f"[Connection issue — check your API key. Error: {e}]"
