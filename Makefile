# A股全栈数据工具包 - Makefile

.PHONY: help install install-web install-dev install-all build clean test run docker-up docker-down

# 默认目标
help:
	@echo "A股全栈数据工具包 - 可用命令:"
	@echo ""
	@echo "  make install       安装项目 (基础依赖)"
	@echo "  make install-web   安装项目 (含 Web 依赖)"
	@echo "  make install-dev   安装项目 (含开发依赖)"
	@echo "  make install-all   安装项目 (含所有依赖)"
	@echo ""
	@echo "  make run           运行 Web 服务"
	@echo "  make test          运行测试"
	@echo ""
	@echo "  make docker-up     启动 Docker 容器"
	@echo "  make docker-down   停止 Docker 容器"
	@echo "  make docker-build  构建 Docker 镜像"
	@echo ""
	@echo "  make build         构建分发包"
	@echo "  make clean         清理构建文件"

# 安装
install:
	pip install -e .

install-web:
	pip install -e ".[web]"

install-dev:
	pip install -e ".[dev]"

install-all:
	pip install -e ".[dev,web]"

# 运行
run:
	python -m a_stock_data.web

# 测试
test:
	pytest tests/ -v

# Docker
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d
	@echo "服务已启动: http://localhost:5000"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# 构建
build:
	./build.sh --package

# 清理
clean:
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
