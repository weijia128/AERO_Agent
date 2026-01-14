#!/bin/bash

# AERO_Agent Tools Installation Script
# This script installs all required monitoring tools

echo "🔧 AERO_Agent Monitoring Tools Installer"
echo "========================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. Check prerequisites
print_status "Checking prerequisites..."

# Check if Node.js is installed
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    print_status "✅ Node.js found: $NODE_VERSION"
else
    print_error "❌ Node.js not found"
    echo "Please install Node.js from: https://nodejs.org/"
    exit 1
fi

# Check if npm is installed
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    print_status "✅ npm found: v$NPM_VERSION"
else
    print_error "❌ npm not found"
    exit 1
fi

# Check if Docker is installed
if command -v docker &> /dev/null;
then
    DOCKER_VERSION=$(docker --version)
    print_status "✅ Docker found: $DOCKER_VERSION"

    # Check if Docker is running
    if docker ps &> /dev/null; then
        print_status "✅ Docker is running"
    else
        print_warning "⚠️  Docker is installed but not running"
        echo "Please start Docker Desktop manually"
    fi
else
    print_warning "⚠️  Docker not found (needed for better-ccflare)"
    echo "Install from: https://www.docker.com/products/docker-desktop/"
fi

# Check if UV is installed
if command -v uv &> /dev/null; then
    UV_VERSION=$(uv --version)
    print_status "✅ UV found: $UV_VERSION"
else
    print_warning "⚠️  UV not found (needed for claude-monitor)"
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

echo ""
print_status "Installing tools..."
echo ""

# 2. Install better-ccflare
print_status "Installing better-ccflare..."
if npm list -g better-ccflare &> /dev/null; then
    print_status "✅ better-ccflare already installed"
else
    npm install -g better-ccflare
    if [ $? -eq 0 ]; then
        print_status "✅ better-ccflare installed successfully"
    else
        print_error "❌ Failed to install better-ccflare"
    fi
fi

# 3. Install claude-monitor
print_status "Installing claude-monitor..."
if command -v claude-monitor &> /dev/null; then
    print_status "✅ claude-monitor already installed"
else
    if command -v uv &> /dev/null; then
        uv tool install claude-monitor
        if [ $? -eq 0 ]; then
            print_status "✅ claude-monitor installed successfully"
        else
            print_error "❌ Failed to install claude-monitor"
        fi
    else
        print_error "❌ UV not found, cannot install claude-monitor"
        print_status "Install UV and run this script again"
    fi
fi

echo ""
print_status "Installation complete!"
echo ""

# 4. Verify installations
print_status "Verifying installations..."
echo ""

# Verify better-ccflare
if command -v better-ccflare &> /dev/null; then
    print_status "✅ better-ccflare: $(which better-ccflare)"
else
    print_error "❌ better-ccflare not found in PATH"
fi

# Verify claude-monitor
if command -v claude-monitor &> /dev/null; then
    print_status "✅ claude-monitor: $(which claude-monitor)"
else
    print_error "❌ claude-monitor not found in PATH"
fi

# Verify ccusage
if npx --version &> /dev/null; then
    print_status "✅ npx/ccusage: Available"
else
    print_error "❌ npx not available"
fi

echo ""
print_status "Next Steps:"
echo ""
echo "1️⃣  Start better-ccflare:"
echo "   ./scripts/start-proxy.sh"
echo ""
echo "2️⃣  Or use Docker directly:"
echo "   docker run -d --name better-ccflare -p 8080:8080 ghcr.io/tombii/better-ccflare:latest"
echo ""
echo "3️⃣  Configure environment:"
echo "   export ANTHROPIC_BASE_URL=http://localhost:8080"
echo ""
echo "4️⃣  Test monitoring:"
echo "   ./scripts/quick-check.sh"
echo "   npx ccusage daily"
echo ""
echo "5️⃣  View dashboard:"
echo "   open http://localhost:8080"
echo ""

# 5. Make scripts executable
print_status "Making scripts executable..."
chmod +x scripts/*.sh
print_status "✅ All scripts are now executable"
echo ""

print_status "🎉 Installation complete! Happy monitoring!"
