#!/bin/bash

# Set the name of the virtual environment directory
VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"

# Check if the virtual environment already exists
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# Activate the virtual environment
source "$VENV_DIR/bin/activate"

# Install dependencies
if [ -f "$REQUIREMENTS_FILE" ]; then
  echo "Installing dependencies from $REQUIREMENTS_FILE..."
  pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
else
  echo "Error: $REQUIREMENTS_FILE not found."
  exit 1
fi

echo "Virtual environment setup complete."
