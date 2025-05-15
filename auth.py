#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Querymind Authentication Module

This module provides user authentication functionality for the Querymind application,
including login, registration, guest access, and logout. It uses MySQL for user storage
and bcrypt for secure password hashing. The login interface is styled with a neon-themed
UI, featuring squarish input fields, centered navigation buttons, descriptive text, and
a full-page background image. User IDs are formatted as QM1, QM2, etc., and reused after deletion.
"""

# Standard library imports
from pathlib import Path
import base64
import re
import os

# Third-party imports
import streamlit as st
import bcrypt
import mysql.connector
from mysql.connector import Error
from contextlib import contextmanager

# Local application imports
from Querymind.config import Config

def init_users_db():
    """
    Initialize the users MySQL database with a users table.
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
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.MYSQL_USERS_DB}")
            cursor.execute(f"USE {Config.MYSQL_USERS_DB}")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password VARBINARY(255) NOT NULL
                )
            """)
            connection.commit()
    except Error as e:
        st.error(f"Error initializing users database: {e}", icon="❌")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@contextmanager
def with_users_db_cursor():
    """
    Context manager for users database cursor.
    """
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_USERS_DB
        )
        cursor = connection.cursor()
        yield cursor
        connection.commit()
    except Error as e:
        if connection:
            connection.rollback()
        st.error(f"Database error: {e}", icon="❌")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@contextmanager
def with_conversations_db_cursor():
    """
    Context manager for conversations database cursor.
    """
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_CONVERSATIONS_DB
        )
        cursor = connection.cursor()
        yield cursor
        connection.commit()
    except Error as e:
        if connection:
            connection.rollback()
        st.error(f"Database error: {e}", icon="❌")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def get_next_user_id():
    """
    Generate the next available user_id in QM{n} format.
    """
    with with_users_db_cursor() as cursor:
        cursor.execute("SELECT user_id FROM users")
        user_ids = [row[0] for row in cursor.fetchall()]
        if not user_ids:
            return "QM1"
        numbers = [int(re.match(r"QM(\d+)", uid).group(1)) for uid in user_ids if re.match(r"QM(\d+)", uid)]
        if not numbers:
            return "QM1"
        max_num = max(numbers)
        for i in range(1, max_num + 2):
            if i not in numbers:
                return f"QM{i}"
        return f"QM{max_num + 1}"

def hash_password(password):
    """
    Hash a password using bcrypt.
    Returns bytes object for storage in VARBINARY column.
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def verify_password(password, hashed):
    """
    Verify a password against its hash.
    Handles hashed as bytes or string (converting string to bytes if needed).
    """
    try:
        # Ensure hashed is bytes
        if isinstance(hashed, str):
            hashed = hashed.encode('utf-8')
        elif not isinstance(hashed, bytes):
            raise ValueError("Hashed password must be bytes or string")
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    except Exception as e:
        st.error(f"Password verification error: {str(e)}", icon="❌")
        return False

def register_user(name, username, email, password):
    """
    Register a new user in the database.
    """
    if not name.strip():
        st.error("Name cannot be empty.", icon="❌")
        return False
    if not email or '@' not in email or '.' not in email:
        st.error("Please enter a valid email address.", icon="❌")
        return False
    if len(password) < 8:
        st.error("Password must be at least 8 characters long.", icon="❌")
        return False
    if not re.search(r"[A-Z]", password):
        st.error("Password must contain at least one uppercase letter.", icon="❌")
        return False
    if not re.search(r"[a-z]", password):
        st.error("Password must contain at least one lowercase letter.", icon="❌")
        return False
    if not re.search(r"[0-9]", password):
        st.error("Password must contain at least one digit.", icon="❌")
        return False
    if not re.search(r"[@#$%^&+=]", password):
        st.error("Password must contain at least one special character (@#$%^&+=).", icon="❌")
        return False

    try:
        with with_users_db_cursor() as cursor:
            hashed_password = hash_password(password)
            user_id = get_next_user_id()
            cursor.execute(
                "INSERT INTO users (user_id, name, username, email, password) VALUES (%s, %s, %s, %s, %s)",
                (user_id, name.strip(), username, email.lower(), hashed_password)
            )
            return True
    except mysql.connector.IntegrityError as e:
        if "Duplicate entry" in str(e):
            if "username" in str(e):
                st.error("Username already exists. Please choose a different username.", icon="❌")
            elif "email" in str(e):
                st.error("Email already exists. Please use a different email.", icon="❌")
        else:
            st.error(f"Database error: {str(e)}", icon="❌")
        return False
    except Error as e:
        st.error(f"Database error: {str(e)}", icon="❌")
        return False

def login_user(username, password):
    """
    Authenticate a user and return user details if successful.
    Ensures password hash is treated as bytes.
    """
    try:
        with with_users_db_cursor() as cursor:
            cursor.execute(
                "SELECT user_id, name, username, email, password FROM users WHERE username = %s",
                (username,)
            )
            user = cursor.fetchone()
            if user:
                # Ensure password hash is bytes
                hashed = user[4]
                if isinstance(hashed, str):
                    hashed = hashed.encode('utf-8')
                if verify_password(password, hashed):
                    return {"user_id": user[0], "name": user[1], "username": user[2], "email": user[3]}
            return None
    except Error as e:
        st.error(f"Database error: {str(e)}", icon="❌")
        return None

def delete_user(user_id):
    """
    Delete a user's account and all associated chat sessions.
    """
    try:
        with with_users_db_cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        with with_conversations_db_cursor() as cursor:
            cursor.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
        return True
    except Error as e:
        st.error(f"Database error while deleting account: {str(e)}", icon="❌")
        return False

def show_login_page():
    """
    Display the login or registration page with a neon-themed UI and full-page background image.
    """
    init_users_db()

    if "auth_page" not in st.session_state:
        st.session_state.auth_page = "login"
    if "registration_success" not in st.session_state:
        st.session_state.registration_success = False

    def get_base64_image(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    
    bg_image_path = os.path.join(os.path.dirname(__file__), "static", "background.jpg")
    try:
        bg_image_base64 = get_base64_image(bg_image_path)
        st.markdown(
            f"""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700&display=swap');
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@500&display=swap');
            
            .stApp {{
                background-image: url("data:image/jpeg;base64,{bg_image_base64}");
                background-size: cover;
                background-position: center;
                background-repeat: repeat;
                background-attachment: local;
                min-height: 100vh;
            }}
            [data-testid="stHeader"] {{
                background: rgba(0, 0, 0, 0);
            }}
            [data-testid="stToolbar"] {{
                background: rgba(0, 0, 0, 0);
            }}
            [data-testid="stSidebar"] > div:first-child {{
                background: rgba(0, 0, 0, 0);
            }}
            [data-testid="stAppViewContainer"] {{
                background: transparent;
            }}
            body {{
                font-family: 'Orbitron', 'Arial', sans-serif;
            }}
            section[data-testid="stSidebar"] {{
                display: none;
            }}
            .main {{
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 2rem;
            }}
            .section-header {{
                color: #ff69b4;
                text-shadow: 0 0 6px #ff69b4, 0 0 12px #ffb6c1;
                font-size: 2rem;
                text-align: center;
                margin-bottom: 1.5rem;
            }}
            input[data-testid="stTextInput"] {{
                border-radius: 8px !important;
                border: 2px solid #39ffa2 !important;
                background: rgba(255, 255, 255, 0.1) !important;
                color: #d2f5d0 !important;
                font-family: 'Roboto', sans-serif !important;
                padding: 0.5rem !important;
                margin-bottom: 1rem !important;
            }}
            input[data-testid="stTextInput"]:focus {{
                box-shadow: 0 0 10px #39ffa2, 0 0 20px #39ffa2 !important;
            }}
            button[kind="primary"] {{
                background-color: #39ffa2 !important;
                color: #1e1e1e !important;
                font-family: 'Orbitron', sans-serif !important;
                border-radius: 8px !important;
                border: none !important;
                padding: 0.5rem 1rem !important;
                transition: all 0.3s ease !important;
                display: block !important;
                margin: 1rem auto !important;
                width: 200px !important;
            }}
            button[kind="primary"]:hover {{
                box-shadow: 0 0 15px #39ffa2, 0 0 30px #39ffa2 !important;
                transform: scale(1.05) !important;
            }}
            button[kind="secondary"] {{
                background-color: transparent !important;
                border: 2px solid #ff69b4 !important;
                color: #ff69b4 !important;
                font-family: 'Orbitron', sans-serif !important;
                border-radius: 8px !important;
                padding: 0.5rem 1rem !important;
                transition: all 0.3s ease !important;
                width: 200px !important;
            }}
            button[kind="secondary"]:hover {{
                box-shadow: 0 0 15px #ff69b4, 0 0 30px #ff69b4 !important;
                transform: scale(1.05) !important;
            }}
            .button-container {{
                display: flex;
                justify-content: flex-start;
                gap: 0.5rem;
                margin-top: 1rem;
                padding-left: 1rem;
            }}
            div[data-testid="stAlert"] p {{
                font-family: 'Orbitron', sans-serif !important;
                font-weight: 500;
                font-size: 1rem;
            }}
            .stTextInput {{
                margin: 0 auto;
                width: 300px;
            }}
            .success-message {{
                font-family: 'Orbitron', sans-serif;
                color: yellow;
                text-shadow: 0 0 6px #ff69b4, 0 0 12px #ffb6c1;
                font-size: 2rem;
                text-align: center;
                margin-bottom: 1.5rem;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    except FileNotFoundError:
        st.warning("Background image not found at static/background.jpg. Please ensure the file exists.", icon="⚠️")
        st.markdown(
            """
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700&display=swap');
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@500&display=swap');
            
            body {{
                background: linear-gradient(#1e1e1e, #2a2a2a);
                font-family: 'Orbitron', 'Arial', sans-serif;
            }}
            section[data-testid="stSidebar"] {{
                display: none;
            }}
            .main {{
                background: linear-gradient(#1e1e1e, #2a2a2a);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 2rem;
            }}
            .section-header {{
                color: #ff69b4;
                text-shadow: 0 0 6px #ff69b4, 0 0 12px #ffb6c1;
                font-size: 2rem;
                text-align: center;
                margin-bottom: 1.5rem;
            }}
            input[data-testid="stTextInput"] {{
                border-radius: 8px !important;
                border: 2px solid #39ffa2 !important;
                background: rgba(255, 255, 255, 0.1) !important;
                color: #d2f5d0 !important;
                font-family: 'Roboto', sans-serif !important;
                padding: 0.5rem !important;
                margin-bottom: 1rem !important;
            }}
            input[data-testid="stTextInput"]:focus {{
                box-shadow: 0 0 10px #39ffa2, 0 0 20px #39ffa2 !important;
            }}
            button[kind="primary"] {{
                background-color: #39ffa2 !important;
                color: #1e1e1e !important;
                font-family: 'Orbitron', sans-serif !important;
                border-radius: 8px !important;
                border: none !important;
                padding: 0.5rem 1rem !important;
                transition: all 0.3s ease !important;
                display: block !important;
                margin: 1rem auto !important;
                width: 200px !important;
            }}
            button[kind="primary"]:hover {{
                box-shadow: 0 0 15px #39ffa2, 0 0 30px #39ffa2 !important;
                transform: scale(1.05) !important;
            }}
            button[kind="secondary"] {{
                background-color: transparent !important;
                border: 2px solid #ff69b4 !important;
                color: #ff69b4 !important;
                font-family: 'Orbitron', sans-serif !important;
                border-radius: 8px !important;
                padding: 0.5rem 1rem !important;
                transition: all 0.3s ease !important;
                width: 200px !important;
            }}
            button[kind="secondary"]:hover {{
                box-shadow: 0 0 15px #ff69b4, 0 0 30px #ff69b4 !important;
                transform: scale(1.05) !important;
            }}
            .button-container {{
                display: flex;
                justify-content: flex-start;
                gap: 0.5rem;
                margin-top: 1rem;
                padding-left: 1rem;
            }}
            div[data-testid="stAlert"] p {{
                font-family: 'Orbitron', sans-serif !important;
                font-weight: 500;
                font-size: 1rem;
            }}
            .stTextInput {{
                margin: 0 auto;
                width: 300px;
            }}
            .success-message {{
                font-family: 'Orbitron', sans-serif;
                color: yellow;
                text-shadow: 0 0 6px #ff69b4, 0 0 12px #ffb6c1;
                font-size: 2rem;
                text-align: center;
                margin-bottom: 1.5rem;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

    with st.container():
        st.markdown("""
            <div style="text-align: center;">
                <h1 style="color: #39ffa2; text-shadow: 0 0 8px #39ffa2, 0 0 16px #39ffa2; font-size: 8rem; margin-bottom: 0.2rem;">
                    QueryMind
                </h1>
                <p style="font-family: 'Orbitron', sans-serif; color: #ff69b4; font-size: 1.8rem; font-weight: 600; text-shadow: 0 0 6px #ff69b4, 0 0 12px #ffb6c1; margin: 0 0 0 -1.6rem;">
                    Database Query Assistant
                </p>
                <p style="font-size: 1.1rem; color: #d2f5d0; max-width: 600px; margin: 0 auto 0.5rem auto; text-shadow: 0 0 6px #39ffa2; font-style: italic;">
                    Intelligence that speaks your language to extract insights — Talk to your database using natural language.
                </p>
            </div>
        """, unsafe_allow_html=True)

        if st.session_state.auth_page == "login" and st.session_state.registration_success:
            st.markdown("""
                <p class="success-message">Registration successful! Please log in to continue.</p>
            """, unsafe_allow_html=True)
            st.session_state.registration_success = False

        if st.session_state.auth_page == "login":
            st.markdown("""
                <h3 class="section-header" style="font-family: 'Orbitron', sans-serif;">Login</h3>
            """, unsafe_allow_html=True)

            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")

            if st.button("Login", type="primary"):
                if not username or not password:
                    st.error("Please enter both username and password.", icon="❌")
                else:
                    with st.spinner("Logging in..."):
                        user = login_user(username, password)
                        if user:
                            st.session_state.authenticated = True
                            st.session_state.is_guest = False
                            st.session_state.user = user
                            st.session_state.sidebar_nav = "Database Info"
                            st.success(f"Welcome, {user['name']}!", icon="✅")
                            st.rerun()
                        else:
                            st.error("Invalid username or password.", icon="❌")

            st.markdown('<div class="button-container">', unsafe_allow_html=True)
            col1, col2 = st.columns([5, 2])
            with col1:
                if st.button("Continue as Guest", type="secondary"):
                    st.session_state.authenticated = True
                    st.session_state.is_guest = True
                    st.session_state.user = {"user_id": None, "name": "Guest", "username": "guest", "email": None}
                    st.session_state.sidebar_nav = "Database Info"
                    st.rerun()
            with col2:
                if st.button("Register Account", type="secondary"):
                    st.session_state.auth_page = "register"
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        elif st.session_state.auth_page == "register":
            st.markdown("""
                <h3 class="section-header" style="font-family: 'Orbitron', sans-serif;">Register</h3>
            """, unsafe_allow_html=True)

            name = st.text_input("Full Name", placeholder="Enter your full name")
            username = st.text_input("Username", placeholder="Choose a username")
            email = st.text_input("Email", placeholder="Enter your email")
            password = st.text_input("Password", type="password", placeholder="Choose a password")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm your password")

            if st.button("Create Account", type="primary"):
                if not all([name, username, email, password, confirm_password]):
                    st.error("Please fill in all fields.", icon="❌")
                elif password != confirm_password:
                    st.error("Passwords do not match.", icon="❌")
                else:
                    if register_user(name, username, email, password):
                        st.session_state.registration_success = True
                        st.session_state.auth_page = "login"
                        st.rerun()

            st.markdown('<div class="button-container">', unsafe_allow_html=True)
            if st.button("Back to Login", type="secondary"):
                st.session_state.auth_page = "login"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

def logout():
    """
    Log out the current user and reset session state with a loading state.
    """
    with st.spinner("Logging out..."):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.authenticated = False
        st.session_state.force_login_page = True
        st.rerun()