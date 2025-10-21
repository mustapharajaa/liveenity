#!/bin/bash

# Install Python dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
fi

# Install Node.js dependencies
echo "Installing Node.js dependencies..."
npm install
