#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Database Tools Module for Querymind

This module provides a set of LangChain tools for interacting with SQLite databases,
allowing the LLM to explore database schema and execute queries in a structured way.
"""

# Standard library imports
import sqlite3
from contextlib import contextmanager
from typing import Any, List

# Third-party imports
from langchain.tools import tool
from langchain_core.messages import ToolMessage
from langchain_core.messages.tool import ToolCall
from langchain_core.tools import BaseTool

# Local application imports
from Querymind.config import Config
from Querymind.logging import log, log_panel


def get_available_tools() -> List[BaseTool]:
    """
    Returns all available database tools.
    
    Returns:
        List[BaseTool]: List of all tools that can be used by the agent
    """
    return [list_tables, sample_table, describe_table, execute_sql]


def call_tool(tool_call: ToolCall) -> Any:
    """
    Execute a tool based on a tool call from the LLM.
    
    Args:
        tool_call (ToolCall): Tool call object from LangChain containing
                             name, arguments, and ID
    
    Returns:
        ToolMessage: Message containing the tool's response to be sent back to the LLM
    """
    tools_by_name = {tool.name: tool for tool in get_available_tools()}
    tool = tools_by_name[tool_call["name"]]
    response = tool.invoke(tool_call["args"])
    return ToolMessage(content=response, tool_call_id=tool_call["id"])


@contextmanager
def with_sql_cursor(readonly=True):
    """
    Context manager for SQLite cursor with support for dynamically uploaded databases.
    
    Creates a connection to the current database file and provides a cursor,
    handling connection lifecycle and transaction management.
    
    Args:
        readonly (bool, optional): Whether the operation is read-only.
                                 If False, changes will be committed. Defaults to True.
    
    Yields:
        sqlite3.Cursor: Database cursor for executing SQL commands
        
    Raises:
        FileNotFoundError: If the database file is not found
    """
    if not Config.Path.DATABASE_PATH or not Config.Path.DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database file not found: {Config.Path.DATABASE_PATH}")
        
    conn = sqlite3.connect(Config.Path.DATABASE_PATH)
    cur = conn.cursor()

    try:
        yield cur
        if not readonly:
            conn.commit()
    except Exception:
        if not readonly:
            conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@tool(parse_docstring=True)
def list_tables(reasoning: str) -> str:
    """
    Lists all user-created tables in the database (excludes SQLite system tables).

    Args:
        reasoning: Detailed explanation of why you need to see all tables (relate to the user's query)

    Returns:
        String representation of a list containing all table names
    """
    log_panel(
        title="List Tables Tool",
        content=f"Reasoning: {reasoning}",
    )
    
    try:
        with with_sql_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            )

            tables = [row[0] for row in cursor.fetchall()]
        return str(tables)
    except FileNotFoundError as e:
        log(f"[red]Database file not found: {str(e)}[/red]")
        return "Error: No database has been uploaded yet. Please upload a SQLite database file first."
    except Exception as e:        
        log(f"[red]Error listing tables: {str(e)}[/red]")
        return f"Error listing tables: {str(e)}"


@tool(parse_docstring=True)
def sample_table(reasoning: str, table_name: str, row_sample_size: int) -> str:
    """
    Retrieves a small sample of rows to understand the data structure and content of a specific table.

    Args:
        reasoning: Detailed explanation of why you need to see sample data from this table
        table_name: Exact name of the table to sample (case-sensitive, no quotes needed)
        row_sample_size: Number of rows to retrieve (recommended: 3-5 rows for readability)

    Returns:
        String with one row per line, showing all columns for each row as tuples
    """
    log_panel(
        title="Sample Table Tool",
        content=f"Table: {table_name}\nRows: {row_sample_size}\nReasoning: {reasoning}",
    )

    try:
        with with_sql_cursor() as cursor:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT {row_sample_size};")
            rows = cursor.fetchall()
        return "\n".join([str(row) for row in rows])
    except FileNotFoundError as e:
        log(f"[red]Database file not found: {str(e)}[/red]")
        return "Error: No database has been uploaded yet. Please upload a SQLite database file first."
    except Exception as e:
        log(f"[red]Error sampling table: {str(e)}[/red]")
        return f"Error sampling table: {str(e)}"


@tool(parse_docstring=True)
def describe_table(reasoning: str, table_name: str) -> str:
    """
    Returns detailed schema information about a table (columns, types, constraints).

    Args:
        reasoning: Detailed explanation of why you need to understand this table's structure
        table_name: Exact name of the table to describe (case-sensitive, no quotes needed)

    Returns:
        String containing table schema information
    """
    log_panel(
        title="Describe Table Tool",
        content=f"Table: {table_name}\nReasoning: {reasoning}",
    )

    try:
        with with_sql_cursor() as cursor:
            cursor.execute(f"PRAGMA table_info('{table_name}');")
            rows = cursor.fetchall()
        return "\n".join([str(row) for row in rows])
    except FileNotFoundError as e:
        log(f"[red]Database file not found: {str(e)}[/red]")
        return "Error: No database has been uploaded yet. Please upload a SQLite database file first."
    except Exception as e:
        log(f"[red]Error describing table: {str(e)}[/red]")
        return f"Error describing table: {str(e)}"


@tool(parse_docstring=True)
def execute_sql(reasoning: str, sql_query: str) -> str:
    """
    Executes SQL query and returns the result

    Args:
        reasoning: Explanation of why this query is being run
        sql_query: Complete, properly formatted SQL query

    Returns:
        String with query results, one row per line as tuples
    """
    log_panel(
        title="Execute SQL Tool",
        content=f"Query: {sql_query}\nReasoning: {reasoning}",
    )

    try:
        with with_sql_cursor() as cursor:
            cursor.execute(sql_query)
            rows = cursor.fetchall()
        return "\n".join([str(row) for row in rows])
    except FileNotFoundError as e:
        log(f"[red]Database file not found: {str(e)}[/red]")
        return "Error: No database has been uploaded yet. Please upload a SQLite database file first."
    except Exception as e:
        log(f"[red]Error running query: {str(e)}[/red]")
        return f"Error running query: {str(e)}"