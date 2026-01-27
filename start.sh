#!/bin/zsh
###
 # @Author: weijia128 weijiaye330@gmail.com
 # @Date: 2026-01-26 23:57:59 +0800
 # @LastEditors: weijia128 weijiaye330@gmail.com
 # @LastEditTime: 2026-01-26 23:59:18 +0800
 # @FilePath: /Experimental_Innovation_Project_Evaluation_System/Users/weijia/Library/Mobile Documents/com~apple~CloudDocs/code/ai/claude_demo/AERO_Agent/start.sh
 # @Description: 
### 
set -euo pipefail

# LLM config (DeepSeek via OpenAI-compatible API)
export LLM_PROVIDER="openai"
export LLM_BASE_URL="https://api.deepseek.com/v1"
export LLM_MODEL="deepseek-chat"

if [[ -z "${LLM_API_KEY:-}" ]]; then
  echo "LLM_API_KEY is not set. Please export it before running start.sh"
  echo "Example: export LLM_API_KEY=sk-7379a7b8099a4d6aa043e70a6d3cc0c2"
  exit 1
fi

# Start backend API
exec uvicorn apps.api.main:app --reload
