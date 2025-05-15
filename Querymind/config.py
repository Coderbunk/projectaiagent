#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration Module for Querymind

This module defines configuration settings, model providers, and path management
for the Querymind application. Designed for deployment on Streamlit Cloud with Aiven MySQL.
"""

# Standard library imports
import os
import random
import numpy as np
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Third-party imports
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class ModelProvider(str, Enum):
    """
    Enum representing supported LLM providers.
    
    Attributes:
        OLLAMA: Local model provider
        GROQ: Cloud-based model provider
    """
    OLLAMA = "ollama"
    GROQ = "groq"

@dataclass
class ModelConfig:
    """
    Configuration settings for language models.
    
    Attributes:
        name (str): Name of the model
        temperature (float): Temperature setting for generation
        provider (ModelProvider): The provider of the model
    """
    name: str
    temperature: float
    provider: ModelProvider

# Model configurations for Ollama
QWEN_2_5 = ModelConfig("qwen2.5", 0.0, ModelProvider.OLLAMA)
GEMMA_3 = ModelConfig("gemma3-tools:12b", 0.7, ModelProvider.OLLAMA)
DEEPSEEK = ModelConfig("deepseek-r1:7b", 0.7, ModelProvider.OLLAMA)
SQLCODER = ModelConfig("sqlcoder", 0.7, ModelProvider.OLLAMA)

# Model configurations for Groq
LLAMA_3_3 = ModelConfig("llama-3.3-70b-versatile", 0.4, ModelProvider.GROQ)
LLAMA_4_MAVERICK = ModelConfig("llama-4-maverick-17b-128e-instruct", 0.0, ModelProvider.GROQ)
LLAMA_4_SCOUT = ModelConfig("llama-4-scout-17b-16e-instruct", 0.0, ModelProvider.GROQ)
MIXTRAL_8x7B = ModelConfig("mixtral-8x7b-32768", 0.0, ModelProvider.GROQ)
GEMMA2_9B_IT = ModelConfig("gemma2-9b-it", 0.0, ModelProvider.GROQ)

class Config:
    """
    Main configuration class for the application.
    
    Contains settings for models, API keys, file paths, and MySQL connections.
    For Aiven MySQL, set MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD in .env.
    """
    # Application settings
    SEED = 42
    MODEL = LLAMA_3_3
    OLLAMA_CONTEXT_WINDOW = 2048

    # API keys
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    if not GROQ_API_KEY and MODEL.provider == ModelProvider.GROQ:
        raise ValueError("GROQ_API_KEY is required for Groq provider but not set in .env")

    # MySQL connection settings
    MYSQL_HOST = os.getenv('MYSQL_HOST')
    MYSQL_PORT = os.getenv('MYSQL_PORT', '3306')
    MYSQL_USER = os.getenv('MYSQL_USER')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
    MYSQL_USERS_DB = os.getenv('MYSQL_USERS_DB', 'querymind_users')
    MYSQL_CONVERSATIONS_DB = os.getenv('MYSQL_CONVERSATIONS_DB', 'querymind_conversations')

    # Validate MySQL settings
    for var, name in [
        (MYSQL_HOST, 'MYSQL_HOST'),
        (MYSQL_USER, 'MYSQL_USER'),
        (MYSQL_PASSWORD, 'MYSQL_PASSWORD')
    ]:
        if not var:
            raise ValueError(f"{name} is required but not set in .env")
    
    try:
        MYSQL_PORT = int(MYSQL_PORT)
        if not (1 <= MYSQL_PORT <= 65535):
            raise ValueError
    except ValueError:
        raise ValueError("MYSQL_PORT must be a valid port number (1-65535)")

    class Path:
        """
        Path management for application directories and files.
        """
        APP_HOME = Path(os.getenv("APP_HOME", Path(__file__).parent.parent))
        DATA_DIR = APP_HOME / "data"
        UPLOADED_DB_DIR = DATA_DIR / "uploaded_databases"
        
        # Ensure directory exists
        try:
            UPLOADED_DB_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise OSError(f"Failed to create directory {UPLOADED_DB_DIR}: {str(e)}")
        
        DATABASE_PATH = None

def seed_everything(seed: int = Config.SEED):
    """
    Set random seeds for reproducibility across random and NumPy.
    
    Args:
        seed (int): Seed value for random number generators
    """
    random.seed(seed)
    np.random.seed(seed)