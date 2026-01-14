#!/bin/bash

# AERO_Agent better-ccflare Docker Setup
# This script runs better-ccflare in Docker for macOS

echo "🐳 AERO_Agent better-ccflare Docker Setup"
echo "======================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found!"
    echo "Install Docker Desktop for Mac: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

echo "✅ Docker found"
echo ""

# Stop any existing container
echo "🛑 Stopping any existing better-ccflare containers..."
docker stop better-ccflare 2>/dev/null || true
docker rm better-ccflare 2>/dev/null || true
echo ""

# Pull the latest image
echo "📦 Pulling better-ccflare Docker image..."
docker pull tombii/better-ccflare:latest
echo ""

# Start the container
echo "🚀 Starting better-ccflare container..."
docker run -d \
  --name better-ccflare \
  -p 8080:8080 \
  --restart unless-stopped \
  tombii/better-ccflare:latest
echo ""

# Wait for container to start
echo "⏳ Waiting for service to start..."
sleep 3

# Check if container is running
if docker ps | grep -q better-ccflare; then
    echo "✅ better-ccflare is running!"
    echo ""
    echo "🌐 Access the dashboard:"
    echo "   http://localhost:8080"
    echo ""
    echo "🔧 Configure Claude Code:"
    echo "   export ANTHROPIC_BASE_URL=http://localhost:8080"
    echo ""
    echo "🛑 To stop:"
    echo "   docker stop better-ccflare"
    echo "   docker rm better-ccflare"
    echo ""
    echo "📊 Container status:"
    docker ps | grep better-ccflare
else
    echo "❌ Failed to start better-ccflare"
    echo ""
    echo "🔍 Check logs:"
    echo "   docker logs better-ccflare"
fi
