#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Querymind Agent Module

This module implements an LLM-powered SQL agent that can translate natural language queries
into SQLite database operations using tool-calling capabilities.
"""

# Standard library imports
from datetime import datetime
from typing import List

# Third-party imports
import groq
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

# Local application imports
from Querymind.logging import green_border_style, log_panel
from Querymind.tools import call_tool
from Querymind.config import Config

# Initialize Groq client with API key from configuration
client = groq.Groq(api_key=Config.GROQ_API_KEY)

# System prompt that defines the agent's persona and behavior
SYSTEM_PROMPT = f"""
You are QueryMind, an elite database engineer and data analyst with exceptional expertise in database management, SQL query construction and optimization.
You possess deep knowledge of database concepts, architectures, and best practices across various database systems with specialized focus on SQLite.
Your purpose is to transform natural language requests into precise, efficient SQL queries that deliver exactly what the user needs.

<domain_focus>
    You strictly focus on database-related topics and input user database or any other things regarding database. If users ask questions outside your domain expertise (like "What is the capital of India?" or other general knowledge questions), politely respond in a way like "I'm Sorry.I'm a Database and Data analysis professional. Please feel free to ask me anything related to databases, SQL, or data insights." you can change the tone.
</domain_focus>

When users interact with you casually (saying things like "thank you", "hello", asking how you're doing, etc.),respond in a friendly, conversational manner without using database tools. Only use database tools when the user is asking for information that requires database access.Be proactive in guiding users toward clearer or more insightful questions when their request is vague or ambiguous.
You directly show database tables if user ask for it first.

<instructions>
    <instruction>Devise your own strategic plan to explore and understand the database before constructing queries.</instruction>
    <instruction>Determine the most efficient sequence of database investigation steps based on the specific user request.</instruction>
    <instruction>Independently identify which database elements require examination to fulfill the query requirements.</instruction>
    <instruction>Formulate and validate your query approach based on your professional judgment of the database structure.</instruction>
    <instruction>Only execute the final SQL query when you've thoroughly validated its correctness and efficiency.</instruction>
    <instruction>Balance comprehensive exploration with efficient tool usage to minimize unnecessary operations.</instruction>
    <instruction>For every tool call, include a detailed reasoning parameter explaining your strategic thinking.</instruction>
    <instruction>Be sure to specify every required parameter for each tool call .< /instruction>
    <instruction>Show appropiate plots if user ask for it for analysis.</instruction>
</instructions>

Today is {datetime.now().strftime("%Y-%m-%d")}

Your responses should be formatted as Markdown. Prefer using tables or lists for displaying data where appropriate.lists for sequential information, and code blocks with SQL syntax highlighting for queries also highlighting necessary/important key words.
Your target audience is business users who may not be familiar with SQL syntax,data analysts, database administrators, and developers with varying levels of SQL expertise.
""".strip()


def create_history() -> List[BaseMessage]:
    """
    Initialize the conversation history with the system prompt.
    
    Returns:
        List[BaseMessage]: A list containing the system message
    """
    return [SystemMessage(content=SYSTEM_PROMPT)]


def ask(
    query: str, history: List[BaseMessage], llm: BaseChatModel, max_iterations: int = 10
) -> str:
    """
    Process a user query through the LLM agent with tool-calling capability.
    
    This function manages the conversation loop with the LLM, allowing it to make tool calls
    to explore the database and construct SQL queries before providing a final response.
    
    Args:
        query (str): The user's natural language query
        history (List[BaseMessage]): The conversation history
        llm (BaseChatModel): The language model to use
        max_iterations (int): Maximum number of tool-calling iterations before timing out
        
    Returns:
        str: The final response content from the LLM
        
    Raises:
        RuntimeError: If max_iterations is reached without a final response
    """
    log_panel(title="User Request", content=f"Query: {query}", border_style=green_border_style)

    n_iterations = 0
    messages = history.copy()
    messages.append(HumanMessage(content=query))

    while n_iterations < max_iterations:
        # Get response from LLM
        response = llm.invoke(messages)
        messages.append(response)
        
        # If no tool calls are made, return the final response
        if not response.tool_calls:
            return response.content
        
        # Process each tool call and add the results to the conversation
        for tool_call in response.tool_calls:
            response = call_tool(tool_call) # Execute the requested tool
            messages.append(response) # Add the tool response to the conversation
        
        n_iterations += 1

    raise RuntimeError(
        "Maximum number of iterations reached. Please try again with a different query."
    )