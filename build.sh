#!/bin/bash
#
# A股全栈数据工具包 - 打包脚本
# Usage: ./build.sh [options]
#
# Options:
#   --dev       开发模式安装 (包含 dev 依赖)
#   --web       Web 模式安装 (包含 web 依赖)
#   --all       安装所有依赖
#   --docker    构建 Docker 镜像
#   --package   创建 wheel 分发包
#   --clean     清理构建文件

set -e

PROJECT_NAME="a-stock-data"
VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

echo "=========================================="
echo "  A股全栈数据工具包 - 打包工具 v${VERSION}"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse arguments
MODE=""
BUILD_DOCKER=false
BUILD_PACKAGE=false
CLEAN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            MODE="dev"
            shift
            ;;
        --web)
            MODE="web"
            shift
            ;;
        --all)
            MODE="all"
            shift
            ;;
        --docker)
            BUILD_DOCKER=true
            shift
            ;;
        --package)
            BUILD_PACKAGE=true
            shift
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Usage: $0 [--dev|--web|--all] [--docker] [--package] [--clean]"
            exit 1
            ;;
    esac
done

# Clean
if [ "$CLEAN" = true ]; then
    log_info "清理构建文件..."
    rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .coverage htmlcov/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    log_info "清理完成"
    exit 0
fi

# Install dependencies
if [ -n "$MODE" ]; then
    log_info "安装依赖 (模式: $MODE)..."
    
    case $MODE in
        dev)
            pip install -e ".[dev,web]"
            ;;
        web)
            pip install -e ".[web]"
            ;;
        all)
            pip install -e ".[dev,web]"
            ;;
    esac
    
    log_info "依赖安装完成"
fi

# Build package
if [ "$BUILD_PACKAGE" = true ]; then
    log_info "构建分发包..."
    
    # Build wheel
    python -m build
    
    log_info "分发包已生成在 dist/ 目录:"
    ls -lh dist/
fi

# Build Docker
if [ "$BUILD_DOCKER" = true ]; then
    log_info "构建 Docker 镜像..."
    
    # Build with tag
    docker build -t ${PROJECT_NAME}:latest .
    docker build -t ${PROJECT_NAME}:${VERSION} .
    
    log_info "Docker 镜像构建完成:"
    docker images | grep ${PROJECT_NAME}
fi

echo ""
log_info "打包完成!"
echo ""
echo "下一步:"
echo "  1. 运行服务:     pip install -e \".[web]\" && python -m a_stock_data.web"
echo "  2. 或使用 Docker: docker-compose up -d"
echo "  3. 访问:         http://localhost:5000"
echo ""
