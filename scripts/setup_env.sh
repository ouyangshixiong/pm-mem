#!/bin/bash

# pm-mem 环境设置脚本
# 用于快速设置开发环境

set -e

echo "=========================================="
echo "pm-mem 环境设置脚本"
echo "=========================================="

# 检查Python版本
echo "检查Python版本..."
python --version || { echo "Python未安装"; exit 1; }

# 创建虚拟环境
echo "创建虚拟环境..."
if [ ! -d "venv" ]; then
    python -m venv venv
    echo "虚拟环境已创建"
else
    echo "虚拟环境已存在"
fi

# 激活虚拟环境
echo "激活虚拟环境..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    echo "无法找到虚拟环境激活脚本"
    exit 1
fi

# 升级pip
echo "升级pip..."
pip install --upgrade pip

# 安装依赖
echo "安装依赖..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "requirements.txt 不存在，安装基础依赖..."
    pip install openai pyyaml structlog python-dotenv
fi

# 安装开发依赖
echo "安装开发依赖..."
pip install pytest pytest-cov pytest-mock black flake8 mypy

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p data backups logs configs

# 复制配置文件示例
echo "设置配置文件..."
if [ ! -f "configs/local.yaml" ]; then
    if [ -f "configs/local.yaml.example" ]; then
        cp configs/local.yaml.example configs/local.yaml
        echo "已创建 configs/local.yaml（请根据需要修改）"
    else
        echo "警告: configs/local.yaml.example 不存在"
    fi
else
    echo "configs/local.yaml 已存在"
fi

# 复制环境变量示例
echo "设置环境变量..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "已创建 .env（请设置您的API密钥）"
        echo "重要: 请编辑 .env 文件，设置 DEEPSEEK_API_KEY"
    else
        echo "警告: .env.example 不存在"
    fi
else
    echo ".env 已存在"
fi

echo ""
echo "=========================================="
echo "环境设置完成！"
echo ""
echo "下一步:"
echo "1. 编辑 .env 文件，设置 DEEPSEEK_API_KEY"
echo "2. 编辑 configs/local.yaml，根据需要修改配置"
echo "3. 运行测试: pytest tests/ -v"
echo "4. 运行示例: python examples/basic_usage.py"
echo ""
echo "常用命令:"
echo "• 运行测试: pytest tests/"
echo "• 运行完整测试: pytest tests/ --cov=src"
echo "• 格式化代码: black src/ tests/"
echo "• 代码检查: flake8 src/ tests/"
echo "• 类型检查: mypy src/"
echo "=========================================="