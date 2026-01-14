#!/bin/bash

# AERO_Agent better-ccflare Environment Setup

echo "🔧 AERO_Agent better-ccflare Environment Setup"
echo "============================================="
echo ""

# Check if better-ccflare is running
if docker ps | grep -q better-ccflare; then
    echo "✅ better-ccflare is running!"
else
    echo "❌ better-ccflare is not running"
    echo "Start it with: docker run -d --name better-ccflare -p 8080:8080 ghcr.io/tombii/better-ccflare:latest"
    exit 1
fi

echo ""
echo "🔧 Configuring environment for better-ccflare..."
echo ""

# Export environment variable for current session
export ANTHROPIC_BASE_URL=http://localhost:8080

echo "✅ Environment variable set for current session:"
echo "   ANTHROPIC_BASE_URL=http://localhost:8080"
echo ""

# Check if profile file exists
PROFILE_FILE=""
if [ -f "$HOME/.zshrc" ]; then
    PROFILE_FILE="$HOME/.zshrc"
elif [ -f "$HOME/.bash_profile" ]; then
    PROFILE_FILE="$HOME/.bash_profile"
elif [ -f "$HOME/.bashrc" ]; then
    PROFILE_FILE="$HOME/.bashrc"
fi

if [ -n "$PROFILE_FILE" ]; then
    echo "📝 Adding to $PROFILE_FILE for permanent setup..."

    # Check if already in profile
    if ! grep -q "ANTHROPIC_BASE_URL=http://localhost:8080" "$PROFILE_FILE" 2>/dev/null; then
        echo "" >> "$PROFILE_FILE"
        echo "# AERO_Agent better-ccflare proxy" >> "$PROFILE_FILE"
        echo "export ANTHROPIC_BASE_URL=http://localhost:8080" >> "$PROFILE_FILE"
        echo "✅ Added to $PROFILE_FILE"
    else
        echo "ℹ️  Already in $PROFILE_FILE"
    fi
else
    echo "⚠️  Could not find profile file (.zshrc, .bash_profile, .bashrc)"
fi

echo ""
echo "🌐 Access the dashboard:"
echo "   http://localhost:8080"
echo ""

echo "🔍 Health check:"
curl -s http://localhost:8080/health | jq '.' 2>/dev/null || curl -s http://localhost:8080/health

echo ""
echo "💡 Next steps:"
echo "   1. Open http://localhost:8080 in your browser"
echo "   2. Configure your Claude Code API settings"
echo "   3. Start using Claude Code - usage will be monitored!"
echo ""

echo "🛑 To stop better-ccflare:"
echo "   docker stop better-ccflare"
echo "   docker rm better-ccflare"
