#!/bin/bash

# AERO_Agent Claude Code Proxy Setup
# This script starts the better-ccflare proxy for enhanced Claude Code usage

echo "🚀 Starting AERO_Agent Claude Code Proxy..."
echo "========================================="
echo ""

# Check if better-ccflare is installed
if ! command -v better-ccflare &> /dev/null; then
    echo "❌ better-ccflare not found!"
    echo "Install with: npm install -g better-ccflare"
    exit 1
fi

# Check if Docker is running
if ! docker ps &> /dev/null; then
    echo "❌ Docker is not running!"
    echo ""
    echo "Please start Docker Desktop:"
    echo "  - Click Docker icon in Applications"
    echo "  - Or run: open -a Docker"
    exit 1
fi

# Check if container already exists and is running
if docker ps | grep -q better-ccflare; then
    echo "✅ better-ccflare is already running!"
    echo ""
    echo "🌐 Access the dashboard:"
    echo "   http://localhost:8080"
    echo ""
    echo "🔧 Configuration:"
    echo "   export ANTHROPIC_BASE_URL=http://localhost:8080"
    echo ""
    echo "📊 Container status:"
    docker ps | grep better-ccflare
    exit 0
fi

# Start the proxy in the background
echo "📡 Starting better-ccflare proxy on port 8080..."
docker run -d \
  --name better-ccflare \
  -p 8080:8080 \
  --restart unless-stopped \
  ghcr.io/tombii/better-ccflare:latest

echo "✅ Proxy started!"
echo ""
echo "⏳ Waiting for service to be ready..."
sleep 3

# Check if it's running
if docker ps | grep -q better-ccflare; then
    echo "✅ better-ccflare is running!"
    echo ""
    echo "📋 Next Steps:"
    echo "=============="
    echo ""
    echo "1. 🔧 Configure your Claude Code to use the proxy:"
    echo "   export ANTHROPIC_BASE_URL=http://localhost:8080"
    echo ""
    echo "2. 🌐 Access the Web Dashboard:"
    echo "   Open: http://localhost:8080"
    echo ""
    echo "3. 🔑 Authentication Options:"
    echo "   Option A - OAuth (Recommended):"
    echo "     - Just set ANTHROPIC_BASE_URL=http://localhost:8080"
    echo "     - No API key needed!"
    echo ""
    echo "   Option B - API Key:"
    echo "     export ANTHROPIC_BASE_URL=http://localhost:8080"
    echo "     export ANTHROPIC_API_KEY=your-api-key-here"
    echo ""
    echo "4. 🎯 For your Claude Code sessions:"
    echo "   - Usage will be monitored in real-time"
    echo "   - View analytics at http://localhost:8080"
    echo "   - Multi-account load balancing is automatic"
    echo ""
    echo "🛑 To stop the proxy:"
    echo "   docker stop better-ccflare"
    echo "   docker rm better-ccflare"
    echo ""
    echo "📊 Current proxy status:"
    curl -s http://localhost:8080/health 2>/dev/null || echo "   (Proxy is starting up, check http://localhost:8080)"
else
    echo "❌ Failed to start better-ccflare"
    echo ""
    echo "🔍 Check logs:"
    echo "   docker logs better-ccflare"
fi
