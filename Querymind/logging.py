#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Logging Module for SQLMancer

This module provides enhanced console logging capabilities using Rich library
to display formatted messages and panels with customizable styles.
"""

# Third-party imports
from rich.console import Console
from rich.panel import Panel
from rich.style import Style

# Predefined styles for different log types
blue_border_style = Style(color="#0EA5E9")  # Info style with blue border
green_border_style = Style(color="#10B981")  # Success style with green border

# Initialize Rich console
console = Console()


def log(
    content: str,
):
    """
    Log a simple message to the console.
    
    Args:
        content (str): The message content to be logged
    """
    console.log(content)


def log_panel(
    title: str,
    content: str,
    border_style: Style = blue_border_style,
):
    """
    Log a message within a styled panel with title.
    
    Creates a visually distinct panel around the log message with a title
    and customizable border style.
    
    Args:
        title (str): The title of the panel
        content (str): The message content to display in the panel
        border_style (Style, optional): The style for the panel border.
                                       Defaults to blue_border_style.
    """
    console.log(
        Panel(
            content,
            title=title,
            border_style=border_style,
        )
    )