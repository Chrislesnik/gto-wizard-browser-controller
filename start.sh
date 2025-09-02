#!/bin/bash

echo "🚀 Starting GTO Wizard Browser Controller API..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip3 first."
    exit 1
fi

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "📦 Installing dependencies..."
    pip3 install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies. Please check the error above."
        exit 1
    fi
else
    echo "❌ requirements.txt not found. Please make sure you're in the correct directory."
    exit 1
fi

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
python3 -m playwright install

if [ $? -ne 0 ]; then
    echo "❌ Failed to install Playwright browsers. Please check the error above."
    exit 1
fi

# Start the FastAPI application
echo "🔥 Starting FastAPI server..."
echo "📍 API will be available at: http://localhost:8000"
echo "📖 API documentation will be available at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python3 main.py
