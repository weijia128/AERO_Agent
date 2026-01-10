#!/bin/bash
# ============================================================
# 机场应急响应 Agent - Conda 环境部署脚本
# ============================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 未安装，请先安装 $1"
        exit 1
    fi
}

# ============================================================
# 主流程
# ============================================================

echo "============================================================"
echo " 机场应急响应 Agent - Conda 环境部署"
echo " 融合方案: ReAct Agent + FSM 验证"
echo "============================================================"
echo ""

# 检查 conda 是否安装
print_info "检查 Conda 安装状态..."
check_command conda

# 获取 conda 版本
CONDA_VERSION=$(conda --version)
print_success "检测到 $CONDA_VERSION"

# 环境名称
ENV_NAME="airport-agent"

# 检查环境是否已存在
if conda env list | grep -q "^${ENV_NAME} "; then
    print_warning "环境 ${ENV_NAME} 已存在"
    read -p "是否删除并重新创建? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "删除现有环境..."
        conda env remove -n ${ENV_NAME} -y
    else
        print_info "跳过环境创建，使用现有环境"
        SKIP_CREATE=true
    fi
fi

# 创建环境
if [ -z "$SKIP_CREATE" ]; then
    print_info "创建 Conda 环境: ${ENV_NAME}..."
    
    if [ -f "environment.yml" ]; then
        print_info "使用 environment.yml 创建环境..."
        conda env create -f environment.yml
    else
        print_info "使用 requirements.txt 创建环境..."
        conda create -n ${ENV_NAME} python=3.11 -y
        
        # 激活环境并安装依赖
        print_info "安装依赖..."
        eval "$(conda shell.bash hook)"
        conda activate ${ENV_NAME}
        
        # 安装 conda 包
        conda install -y shapely pyyaml numpy
        
        # 安装 pip 包
        pip install -r requirements.txt
    fi
    
    print_success "环境创建完成"
fi

# 配置环境变量
print_info "配置环境变量..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_warning "已创建 .env 文件，请编辑填入 API Key"
    else
        cat > .env << 'EOF'
# LLM 配置
LLM_PROVIDER=zhipu
LLM_MODEL=glm-4
LLM_API_KEY=your-api-key-here
LLM_TEMPERATURE=0.1

# Agent 配置
MAX_ITERATIONS=15
DEBUG=true

# API 配置
API_HOST=0.0.0.0
API_PORT=8000
EOF
        print_warning "已创建 .env 文件，请编辑填入 API Key"
    fi
else
    print_info ".env 文件已存在"
fi

# 验证安装
print_info "验证安装..."
eval "$(conda shell.bash hook)"
conda activate ${ENV_NAME}

python -c "
import sys
print(f'Python 版本: {sys.version}')

# 检查关键依赖
deps = [
    ('langgraph', 'LangGraph'),
    ('langchain', 'LangChain'),
    ('fastapi', 'FastAPI'),
    ('pydantic', 'Pydantic'),
    ('shapely', 'Shapely'),
]

all_ok = True
for module, name in deps:
    try:
        __import__(module)
        print(f'  ✓ {name}')
    except ImportError:
        print(f'  ✗ {name} - 未安装')
        all_ok = False

if all_ok:
    print('\\n所有依赖已正确安装!')
else:
    print('\\n部分依赖缺失，请检查安装')
    sys.exit(1)
"

print_success "安装验证完成"

# 打印使用说明
echo ""
echo "============================================================"
echo " 部署完成!"
echo "============================================================"
echo ""
echo "使用方法:"
echo ""
echo "  1. 激活环境:"
echo "     conda activate ${ENV_NAME}"
echo ""
echo "  2. 配置 API Key:"
echo "     编辑 .env 文件，填入 LLM_API_KEY"
echo ""
echo "  3. 运行演示:"
echo "     python run_demo.py"
echo ""
echo "  4. 启动 API 服务:"
echo "     python -m apps.api.main"
echo "     # 或"
echo "     uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "  5. 运行测试:"
echo "     pytest tests/ -v"
echo ""
echo "  6. API 文档:"
echo "     http://localhost:8000/docs"
echo ""
echo "============================================================"
