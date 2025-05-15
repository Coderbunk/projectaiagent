#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Querymind Web Application Module

This module implements a Streamlit-based web interface for the Querymind database
query assistant. It allows users to upload SQLite databases, interact with them
using natural language queries, and manage chat sessions via a sidebar with
navigation tabs for Database Info, Chat History, and Settings. Sample questions are shown
horizontally for new users after database upload. Includes authentication for
guest and registered users.

Designed for deployment on Streamlit Cloud with Aiven MySQL.
"""

# Standard library imports
import os
import random
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

# Third-party imports
import streamlit as st
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import mysql.connector
from mysql.connector import Error

# Local application imports
from Querymind.config import Config
from Querymind.models import create_llm
from Querymind.tools import get_available_tools, with_sql_cursor
from Querymind.agent import ask, create_history
from auth import init_users_db, show_login_page, logout, delete_user, with_conversations_db_cursor

# Set page configuration
favicon_path = os.path.join(os.path.dirname(__file__), "static", "logo2.png")
if not os.path.exists(favicon_path):
    st.warning(f"Favicon file not found at {favicon_path}. Using default Streamlit icon.", icon="⚠️")
    favicon_path = None

st.set_page_config(
    page_title="QueryMind",
    page_icon=favicon_path,
    layout="centered",
    initial_sidebar_state="expanded",
)

# Immediate authentication check
if (
    st.session_state.get("force_login_page", False)
    or not st.session_state.get("authenticated", False)
):
    show_login_page()
    st.session_state.force_login_page = False
    st.stop()

# Load environment variables
load_dotenv()

# Initialize database path
Config.Path.DATABASE_PATH = None

# Loading messages for query processing
LOADING_MESSAGES = [
    "Consulting the ancient tomes of SQL wisdom ... ",
    "Casting query spells on your database ... ",
    "Summoning data from the digital realms ... ",
    "Deciphering your request into database runes ... ",
    "Brewing a potion of perfect query syntax ... ",
    "Channeling the power of database magic ... ",
    "Translating your words into the language of tables ... ",
    "Waving my SQL wand to fetch your results ... ",
    "Performing database divination ... ",
    "Aligning the database stars for optimal results ... ",
    "Consulting with the database spirits ... ",
    "Transforming natural language into database incantations ... ",
    "Peering into the crystal ball of your database ... ",
    "Opening a portal to your data dimension ... ",
    "Enchanting your request with SQL magic ... ",
    "Invoking the ancient art of query optimization ... ",
    "Reading between the tables to find your answer ... ",
    "Conjuring insights from your database depths ... ",
    "Weaving a tapestry of joins and filters ... ",
    "Preparing a feast of data for your consideration ... ",
]

def init_conversations_db():
    """
    Initialize the conversations MySQL database and ensure correct schema.
    Requires MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD in .env.
    """
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD
        )
        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.MYSQL_CONVERSATIONS_DB}")
            cursor.execute(f"USE {Config.MYSQL_CONVERSATIONS_DB}")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    user_id VARCHAR(255),
                    title TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    conversation_json TEXT NOT NULL
                )
            """)
            connection.commit()
    except Error as e:
        st.error(f"Error initializing conversations database: {e}", icon="❌")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def save_session(session_id, title, messages):
    """
    Save or update a chat session in the conversations database for authenticated users.
    """
    if st.session_state.is_guest:
        return None
    user_id = st.session_state.user.get("user_id")
    if user_id is None:
        st.error("Cannot save session: Invalid user ID.", icon="❌")
        return None
    serialized_messages = [
        {"type": msg.__class__.__name__, "content": msg.content}
        for msg in messages
        if not isinstance(msg, SystemMessage)
    ]
    try:
        with with_conversations_db_cursor() as cursor:
            if session_id is None:
                current_time = datetime.now().strftime("%d-%m-%y [%H:%M]")
                title = f"Chat@{current_time}"
                cursor.execute(
                    "INSERT INTO sessions (user_id, title, created_at, conversation_json) VALUES (%s, %s, %s, %s)",
                    (user_id, title, datetime.now(), json.dumps(serialized_messages))
                )
                return cursor.lastrowid
            else:
                cursor.execute(
                    "UPDATE sessions SET title = %s, conversation_json = %s WHERE session_id = %s AND user_id = %s",
                    (title, json.dumps(serialized_messages), session_id, user_id)
                )
                return session_id
    except Error as e:
        st.error(f"Database error while saving session: {str(e)}", icon="❌")
        return None

def load_session(session_id):
    """
    Load a chat session from the conversations database.
    """
    if st.session_state.is_guest:
        return create_history()
    user_id = st.session_state.user.get("user_id")
    if user_id is None:
        return create_history()
    try:
        with with_conversations_db_cursor() as cursor:
            cursor.execute(
                "SELECT conversation_json FROM sessions WHERE session_id = %s AND user_id = %s",
                (session_id, user_id)
            )
            result = cursor.fetchone()
            if result:
                messages = json.loads(result[0])
                history = create_history()
                for msg in messages:
                    if msg["type"] == "HumanMessage":
                        history.append(HumanMessage(content=msg["content"]))
                    elif msg["type"] == "AIMessage":
                        history.append(AIMessage(content=msg["content"]))
                return history
            return create_history()
    except Error as e:
        st.error(f"Database error while loading session: {str(e)}", icon="❌")
        return create_history()

def delete_session(session_id):
    """
    Delete a chat session from the conversations database.
    """
    if st.session_state.is_guest:
        return
    user_id = st.session_state.user.get("user_id")
    if user_id is None:
        return
    try:
        with with_conversations_db_cursor() as cursor:
            cursor.execute(
                "DELETE FROM sessions WHERE session_id = %s AND user_id = %s",
                (session_id, user_id)
            )
        if "current_session_id" in st.session_state and st.session_state.current_session_id == session_id:
            new_session_id = save_session(None, "", create_history())
            st.session_state.current_session_id = new_session_id
            st.session_state.session_title = f"Chat@{datetime.now().strftime('%d-%m-%y [%H:%M]')}"
            st.session_state.messages = create_history()
    except Error as e:
        st.error(f"Database error while deleting session: {str(e)}", icon="❌")

def list_sessions():
    """
    List all chat sessions for the current user.
    """
    if st.session_state.is_guest:
        return []
    user_id = st.session_state.user.get("user_id")
    if user_id is None:
        return []
    try:
        with with_conversations_db_cursor() as cursor:
            cursor.execute(
                "SELECT session_id, title, created_at FROM sessions WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,)
            )
            sessions = [
                (session_id, title, datetime.strptime(str(created_at), "%Y-%m-%d %H:%M:%S").strftime("%d-%m-%y [%H:%M]"))
                for session_id, title, created_at in cursor.fetchall()
            ]
            return sessions
    except Error as e:
        st.error(f"Database error while listing sessions: {str(e)}", icon="❌")
        return []

def reset_model_cache():
    """
    Reset the cached LLM model in session state.
    """
    if 'model' in st.session_state:
        del st.session_state['model']

@st.cache_resource(show_spinner=False)
def get_model() -> BaseChatModel:
    """
    Create and cache an LLM instance with database tools bound.
    """
    llm = create_llm(Config.MODEL)
    llm = llm.bind_tools(get_available_tools())
    return llm

def load_css(css_file):
    """
    Load and apply CSS styling from an external file.
    """
    try:
        css_path = os.path.join(os.path.dirname(__file__), css_file)
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"CSS file not found at {css_file}. Default styling applied.", icon="⚠️")

def save_uploaded_file(uploaded_file):
    """
    Save an uploaded database file to the configured directory.
    """
    file_path = Config.Path.UPLOADED_DB_DIR / uploaded_file.name
    try:
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        with sqlite3.connect(file_path) as conn:
            conn.cursor().execute("SELECT 1")
    except (sqlite3.Error, OSError) as e:
        st.error(f"Invalid SQLite database file: {str(e)}", icon="❌")
        if file_path.exists():
            file_path.unlink()
        return None
    Config.Path.DATABASE_PATH = file_path
    reset_model_cache()
    return file_path

def clear_chat():
    """
    Clear the current session's chat history.
    """
    if st.session_state.is_guest:
        st.session_state.messages = create_history()
        return True
    if "messages" in st.session_state and "current_session_id" in st.session_state:
        st.session_state.messages = create_history()
        save_session(
            st.session_state.current_session_id,
            st.session_state.session_title,
            st.session_state.messages
        )
        return True
    return False

# Initialize databases
init_users_db()
init_conversations_db()

# Validate user dictionary for registered users
if not st.session_state.is_guest and (st.session_state.user is None or 'name' not in st.session_state.user or 'user_id' not in st.session_state.user):
    st.error("Invalid user session. Please log in again.", icon="❌")
    logout()
    st.stop()

# Initialize session state for authenticated users
if "current_session_id" not in st.session_state:
    if st.session_state.is_guest:
        st.session_state.current_session_id = None
        st.session_state.session_title = "Guest Session"
        st.session_state.messages = create_history()
    else:
        user_id = st.session_state.user.get("user_id")
        if user_id is None:
            st.error("Invalid user ID. Please log in again.", icon="❌")
            logout()
            st.stop()
        new_session_id = save_session(None, "", create_history())
        if new_session_id is None:
            st.session_state.current_session_id = None
            st.session_state.session_title = "Temporary Session"
            st.session_state.messages = create_history()
        else:
            st.session_state.current_session_id = new_session_id
            st.session_state.session_title = f"Chat@{datetime.now().strftime('%d-%m-%y [%H:%M]')}"
            st.session_state.messages = create_history()
if "has_interacted" not in st.session_state:
    st.session_state.has_interacted = False

# Ensure messages is initialized
if "messages" not in st.session_state or st.session_state.messages is None:
    if st.session_state.is_guest:
        st.session_state.messages = create_history()
    elif "current_session_id" in st.session_state:
        st.session_state.messages = load_session(st.session_state.current_session_id)
    else:
        st.session_state.messages = create_history()

# Initialize sample question queue
if "pending_sample_question" not in st.session_state:
    st.session_state.pending_sample_question = None

# Load custom CSS
load_css("assets/style.css")

# Application Header
welcome_text = "Guest User" if st.session_state.is_guest else f"{st.session_state.user.get('name', 'Unknown User')} (user_id: {st.session_state.user.get('user_id', 'N/A')})"
st.markdown(f"""
<div style="text-align: center;">
    <h1 style="color: #39ffa2; text-shadow: 0 0 8px #39ffa2, 0 0 16px #39ffa2; font-size: 6rem; margin-bottom: 0.2rem;">
        QueryMind
    </h1>
    <p style="font-family: 'Orbitron', sans-serif; color: #ff69b4; font-size: 1.8rem; font-weight: 600; text-shadow: 0 0 6px #ff69b4, 0 0 12px #ffb6c1; margin: 0 0 0 -1.6rem;">
        Database Query Assistant
    </p>
    <p style="font-size: 1.1rem; color: #d2f5d0; max-width: 600px; margin: 0 auto 0.5rem; text-shadow: 0 0 6px #39ffa2; font-style: italic;">
        Intelligence that speaks your language to extract insights — Talk to your database using natural language.
    </p>
    <p style="font-family: 'Orbitron', sans-serif; font-size: 1rem; color: yellow; margin: 0.5rem auto 3rem; text-shadow: 0 0 9px #39ffa2;">
        Welcome, {welcome_text}
    </p>
</div>
""", unsafe_allow_html=True)

# File Uploader
st.markdown('<div style="padding: 1rem 0;">', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Upload SQLite Database", type=["sqlite", "db", "sqlite3"], label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)

# Custom font styling for alerts
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700&display=swap');
        div[data-testid="stAlert"] p {
            font-family: 'Orbitron', sans-serif !important;
            font-weight: 500;
            font-size: 1rem;
            color: rgba(255, 255, 255, 0.5) !important;
        }
    </style>
""", unsafe_allow_html=True)

# === Database Upload Handling ===
if uploaded_file is not None:
    db_path = save_uploaded_file(uploaded_file)
    if db_path:
        st.success("Database uploaded! 👏 Check the sidebar for table details.👈")
    else:
        st.error("Failed to upload database. Please try again.", icon="❌")
else:
    st.warning("Please upload a database file to proceed.", icon="⚠️")

# === Sidebar: Navigation Tabs ===
with st.sidebar:
    st.markdown('<div class="nav-buttons">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([0.95, 0.7, 0.89])
    with col1:
        if st.button("Database Info", key="nav_db_info"):
            st.session_state.sidebar_nav = "Database Info"
    with col3:
        if st.button("Chat History", key="nav_chat_history"):
            st.session_state.sidebar_nav = "Chat History"
    with col2:
        if st.button("Settings", key="nav_settings"):
            st.session_state.sidebar_nav = "Settings"
    
    st.markdown('</div>', unsafe_allow_html=True)

    if "sidebar_nav" not in st.session_state:
        st.session_state.sidebar_nav = "Database Info"
    st.markdown(f"""
        <style>
            button[data-testid="baseButton-primary"]:has(span:contains("{st.session_state.sidebar_nav}")) {{
                background-color: #39ffa2 !important;
                color: #1e1e1e !important;
                border: none !important;
                box-shadow: 0 0 10px #39ffa2 !important;
                font-family: 'Orbitron', sans-serif !important;
            }}
        </style>
    """, unsafe_allow_html=True)

    if st.session_state.sidebar_nav == "Database Info":
        st.markdown("""
            <div class="card sidebar-header">
                <h2 class="glow-header db-details">📊 Database Info</h2>
                <p class="tagline">Explore your database tables and details.</p>
            </div>
        """, unsafe_allow_html=True)

        if Config.Path.DATABASE_PATH and Config.Path.DATABASE_PATH.exists():
            st.markdown("""
                <div class="card sidebar-header">
                    <h3 class="glow-header db-details">📊 Database Details</h3>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
                <p class="db-info-text"><strong>File:</strong> {Config.Path.DATABASE_PATH.name}</p>
            """, unsafe_allow_html=True)

            db_size = Config.Path.DATABASE_PATH.stat().st_size / (1024 * 1024)
            st.markdown(f"""
                <p class="db-info-text"><strong>Size:</strong> {db_size:.2f} MB</p>
            """, unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

            try:
                with with_sql_cursor() as cursor:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    if tables:
                        st.markdown("""
                            <div class="card sidebar-header">
                                <h3 class="glow-header db-details">📋 Available Tables</h3>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        with st.expander("View Tables", expanded=True):
                            for table in tables:
                                # Validate table name
                                cursor.execute(
                                    "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                                    (table,)
                                )
                                if cursor.fetchone():
                                    cursor.execute(f"SELECT count(*) FROM [{table}]")
                                    count = cursor.fetchone()[0]
                                    st.markdown(f"""
                                        <div class="table-item">
                                            <span>{table}</span>
                                            <span class="row-count">{count} rows</span>
                                        </div>
                                    """, unsafe_allow_html=True)
                                else:
                                    st.warning(f"Table {table} not found.", icon="⚠️")
                    else:
                        st.warning("No tables found in the database.", icon="⚠️")
            except sqlite3.Error as e:
                st.error(f"Error reading database: {str(e)}", icon="❌")
        else:
            st.markdown("""
                <div class="card sidebar-header">
                    <h2 class="glow-header db-details">📃 Ready to Query?</h2>
                    <p class="tagline">Upload an SQLite database to explore its tables and start querying!</p>
                    <p class="hint" style="font-family: 'Audiowide', sans-serif; font-size: 0.9rem;">
                        Supported formats: .sqlite, .db, .sqlite3
                    </p>
                </div>
            """, unsafe_allow_html=True)

    elif st.session_state.sidebar_nav == "Chat History":
        st.markdown("""
            <div class="card chat-sidebar">
                <h2 class="glow-header db-details">Chat History</h2>
                <p class="tagline">Manage your chat sessions.</p>
            </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([1.47, 2.8])
        with col2:
            st.markdown('<div class="new-chat-container">', unsafe_allow_html=True)
            if st.button("New Chat", key="new_chat", type="primary"):
                if st.session_state.is_guest:
                    st.session_state.current_session_id = None
                    st.session_state.session_title = "Guest Session"
                    st.session_state.messages = create_history()
                else:
                    new_session_id = save_session(None, "", create_history())
                    st.session_state.current_session_id = new_session_id
                    st.session_state.session_title = f"Chat@{datetime.now().strftime('%d-%m-%y [%H:%M]')}"
                    st.session_state.messages = create_history()
                st.session_state.has_interacted = False
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        sessions = list_sessions()
        if sessions:
            st.markdown("<h3 class='glow-header db-details'>Previous Chats</h3>", unsafe_allow_html=True)
            for session_id, title, created_at in sessions:
                col1, col2 = st.columns([4, 1])
                with col1:
                    button_type = "primary" if session_id == st.session_state.current_session_id else "secondary"
                    if st.button(
                        f"{title}",
                        key=f"session_{session_id}",
                        help=title,
                        type=button_type
                    ):
                        st.session_state.current_session_id = session_id
                        st.session_state.session_title = title
                        st.session_state.messages = load_session(session_id)
                        st.session_state.has_interacted = False
                        st.rerun()
                with col2:
                    if st.button("🗑️", key=f"delete_{session_id}"):
                        delete_session(session_id)
                        st.rerun()
        else:
            st.info("ℹ️ Log in to access chat sessions.")

    elif st.session_state.sidebar_nav == "Settings":
        st.markdown("""
            <div class="card sidebar-header">
                <h2 class="glow-header db-details">⚙️ Settings</h2>
                <p class="tagline">Manage your account and session.</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="settings-button-container">', unsafe_allow_html=True)
        col1, col2 = st.columns([3.4, 1])
        with col2:
            if st.button("Logout", key="logout", help="Log out of your account", type="primary"):
                logout()
        with col1:
            if not st.session_state.is_guest:
                if st.button("Delete Account", key="delete_account", help="Permanently delete your account and all associated data", type="tertiary"):
                    user_id = st.session_state.user.get("user_id")
                    if user_id and delete_user(user_id):
                        logout()
                    else:
                        st.error("Failed to delete account.", icon="❌")
        st.markdown('</div>', unsafe_allow_html=True)

# Clear Chat Button
col1, col2 = st.columns([2.3, 3])
with col2:
    if st.button("Clear Chat", type="secondary"):
        if clear_chat():
            st.session_state.has_interacted = False
            st.rerun()

st.markdown("<hr style='border: 1px solid rgba(57, 255, 162, 0.3); margin: 15px 0;'>", unsafe_allow_html=True)

# === Main Content: Chat Interface ===
sample_container = st.container()
if Config.Path.DATABASE_PATH and Config.Path.DATABASE_PATH.exists() and not st.session_state.has_interacted:
    with sample_container:
        sample_questions = [
            "List all tables in the database.",
            "Describe the database schema.",
            "Summarize the database structure.",
            "Show relations between tables.",
            "Show top 5 rows of all tables"
        ]

        st.markdown('<div class="new-chat-container">', unsafe_allow_html=True)
        cols = st.columns(len(sample_questions))
        for idx, question in enumerate(sample_questions):
            with cols[idx]:
                if st.button(question, key=f"sample_{idx}", help=question, type="secondary"):
                    st.session_state.has_interacted = True
                    st.session_state.pending_sample_question = question
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.pending_sample_question:
    question = st.session_state.pending_sample_question
    st.session_state.messages.append(HumanMessage(content=question))
    if not st.session_state.is_guest:
        save_session(
            st.session_state.current_session_id,
            st.session_state.session_title,
            st.session_state.messages
        )
    if not Config.Path.DATABASE_PATH or not Config.Path.DATABASE_PATH.exists():
        st.session_state.pending_sample_question = None
        st.error("Please upload a valid SQLite database file first.", icon="❌")
    else:
        try:
            response = ask(question, st.session_state.messages, get_model())
            st.session_state.messages.append(AIMessage(content=response))
            if not st.session_state.is_guest:
                save_session(
                    st.session_state.current_session_id,
                    st.session_state.session_title,
                    st.session_state.messages
                )
            st.session_state.pending_sample_question = None
            st.rerun()
        except Exception as e:
            st.session_state.pending_sample_question = None
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["limit exceeded", "rate limit", "quota exceeded"]):
                st.error(f"Usage limit exceeded. Please try again later or upgrade your plan. Error: {str(e)}", icon="⚠️")
            else:
                st.error(f"Error processing your request: {str(e)}", icon="❌")

if st.session_state.messages is not None:
    for message in st.session_state.messages:
        if isinstance(message, SystemMessage):
            continue
        is_user = isinstance(message, HumanMessage)
        avatar = "🧐" if is_user else "🤖"
        with st.chat_message("user" if is_user else "ai", avatar=avatar):
            st.markdown(message.content)

if st.session_state.pending_sample_question:
    with st.chat_message("ai", avatar="🤖"):
        message_placeholder = st.empty()
        message_placeholder.status(random.choice(LOADING_MESSAGES), state="running")

if prompt := st.chat_input("Type your message ... "):
    st.session_state.has_interacted = True
    st.session_state.messages.append(HumanMessage(content=prompt))
    if not st.session_state.is_guest:
        save_session(
            st.session_state.current_session_id,
            st.session_state.session_title,
            st.session_state.messages
        )

    with st.chat_message("ai", avatar="🤖"):
        message_placeholder = st.empty()
        message_placeholder.status(random.choice(LOADING_MESSAGES), state="running")

        if not Config.Path.DATABASE_PATH or not Config.Path.DATABASE_PATH.exists():
            message_placeholder.empty()
            st.error("Please upload a valid SQLite database file first.", icon="❌")
        else:
            try:
                response = ask(prompt, st.session_state.messages, get_model())
                message_placeholder.markdown(response)
                st.session_state.messages.append(AIMessage(content=response))
                if not st.session_state.is_guest:
                    save_session(
                        st.session_state.current_session_id,
                        st.session_state.session_title,
                        st.session_state.messages
                    )
                st.rerun()
            except Exception as e:
                message_placeholder.empty()
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ["limit exceeded", "rate limit", "quota exceeded"]):
                    st.error(f"Usage limit exceeded. Please try again later or upgrade your plan. Error: {str(e)}", icon="⚠️")
                else:
                    st.error(f"Error processing your request: {str(e)}", icon="❌")
