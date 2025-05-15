#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Model Provider Module for Querymind

This module handles the configuration and instantiation of different language models
from various providers (Ollama, Groq) using the LangChain framework.
"""

# Third-party imports
import groq
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

# Local application imports
from Querymind.config import Config, ModelConfig, ModelProvider

# Initialize Groq client with API key from configuration
client = groq.Groq(api_key=Config.GROQ_API_KEY)


def create_llm(model_config: ModelConfig) -> BaseChatModel:
    """
    Create and configure a language model based on the provided configuration.
    
    Factory function that instantiates the appropriate LangChain chat model
    based on the specified provider (Ollama or Groq).
    
    Args:
        model_config (ModelConfig): Configuration for the model including
                                   name, temperature, and provider
    
    Returns:
        BaseChatModel: Configured language model instance ready for use
    """
    if model_config.provider == ModelProvider.OLLAMA:
        return ChatOllama(
            model=model_config.name,
            temperature=model_config.temperature,
            num_ctx=Config.OLLAMA_CONTEXT_WINDOW,
            verbose=False,
            keep_alive=-1,
        )
    elif model_config.provider == ModelProvider.GROQ:
        return ChatGroq(model=model_config.name, temperature=model_config.temperature)