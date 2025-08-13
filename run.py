#!/usr/bin/env python3
"""
Simple wrapper script to run the Discord Music Bot
"""

import os
import sys

# Add the current directory to the path so we can import from src
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the main function from the main module
from src.main import main

if __name__ == "__main__":
    # Run the main function
    import asyncio
    asyncio.run(main()) 