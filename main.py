#!/usr/bin/env python
# -*- coding: utf-8 -*-


#SQLMancer CLI Interface
#Run this script to use SQLMancer from the command line instead of the web interface.
#In terminal run this : python main.py C:\Users\LENOVO\Your database path 



import os
import sys
from pathlib import Path

# Local application imports
from Querymind.config import Config
from Querymind.models import create_llm
from Querymind.tools import get_available_tools
from Querymind.agent import ask, create_history

def main():
    # Check if database path was provided
    if len(sys.argv) < 2:
        print("Usage: python cli.py [path_to_sqlite_database]")
        sys.exit(1)
    
    # Set database path
    db_path = Path(sys.argv[1])
    if not db_path.exists():
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)
    
    Config.Path.DATABASE_PATH = db_path
    print(f"Connected to database: {db_path}")
    
    # Initialize the model
    llm = create_llm(Config.MODEL)
    llm = llm.bind_tools(get_available_tools())
    
    # Create history with system prompt
    history = create_history()
    
    # Interactive loop
    try:
        while True:
            # Get user query
            query = input("\n🧐 Enter your query (or 'exit' to quit): ")
            
            if query.lower() in ('exit', 'quit'):
                print("Goodbye! 👋")
                break
                
            print("\n🤖 Processing...")
            
            # Process the query
            try:
                response = ask(query, history, llm)
                print(f"\n🤖 Response:\n{response}")
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")
    
    except KeyboardInterrupt:
        print("\nGoodbye! 👋")

if __name__ == "__main__":
    main()