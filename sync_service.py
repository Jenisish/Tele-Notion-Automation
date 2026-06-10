#!/usr/bin/env python3
"""Entry point for the sync service — runs from any directory."""
import sys
import os

# Ensure the project root is on sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.sync import run_loop

if __name__ == "__main__":
    run_loop()
