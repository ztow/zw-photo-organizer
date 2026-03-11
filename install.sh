#!/bin/bash
# zw-photo-organizer 一键安装脚本

set -e

echo "🚀 安装 zw-photo-organizer..."

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 需要 Python3"
    exit 1
fi

# 安装目录
INSTALL_DIR="${HOME}/.openclaw/skills/zw-photo-organizer"

# 克隆仓库
echo "📥 下载代码..."
if [ -d "$INSTALL_DIR" ]; then
    echo "⚠️  目录已存在，更新代码..."
    cd "$INSTALL_DIR"
    git pull
else
    git clone https://github.com/ztow/zw-photo-organizer.git "$INSTALL_DIR"
fi

# 安装依赖
echo "📦 安装依赖..."
pip3 install Pillow --break-system-packages 2>/dev/null || pip3 install Pillow --user

# 创建命令别名
echo "🔗 创建命令..."
mkdir -p ~/.local/bin
cat > ~/.local/bin/zphoto << 'EOF'
#!/bin/bash
python3 ~/.openclaw/skills/zw-photo-organizer/scripts/organize.py "$@"
EOF
chmod +x ~/.local/bin/zphoto

# 检查 PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "⚠️  请将 ~/.local/bin 添加到 PATH"
    echo "   添加到 ~/.bashrc 或 ~/.zshrc:"
    echo '   export PATH="$HOME/.local/bin:$PATH"'
fi

echo ""
echo "✅ 安装完成！"
echo ""
echo "使用方法:"
echo "  zphoto \"/path/to/your/photos\""
echo "  zphoto \"/path/to/your/photos\" --dry-run  # 预览模式"
echo ""
echo "项目地址: https://github.com/ztow/zw-photo-organizer"
