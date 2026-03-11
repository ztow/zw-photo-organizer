# zw-photo-organizer

> 赵兄的智能照片整理 - 一个支持四级日期识别的照片自动分类工具

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## ✨ 功能特性

- 📅 **四级日期识别** - 智能识别照片拍摄日期
  - Level 1: 文件名（如 `IMG_20241003_143022.jpg`）
  - Level 2: 上级目录（如 `哈尔滨市, 2025年2月12日/`）
  - Level 3: EXIF 元数据
  - Level 4: 文件修改时间（mtime）
  
- 📁 **三层嵌套结构** - 年/月/日 自动分类
  ```
  2024/
  └── 2024_11/
      └── 2024_11_08/
          └── IMG_0001.JPG
  ```

- 📝 **自动生成索引** - 整理完成后生成 Markdown 清单

- 🛡️ **安全操作** - 只移动不删除，拿不准的照片单独存放

- 🔍 **重复检测** - 检测同名文件和重复文件

---

## 📦 安装

### 方式一：直接克隆（推荐）

```bash
# 1. 克隆到本地
git clone https://github.com/ztow/zw-photo-organizer.git

# 2. 进入目录
cd zw-photo-organizer

# 3. 安装依赖
pip3 install -r requirements.txt
# 或
pip3 install Pillow --break-system-packages

# 4. 运行
python3 scripts/organize.py "/path/to/your/photos"
```

### 方式二：OpenClaw Skill 安装

```bash
# 克隆到 OpenClaw skills 目录
git clone https://github.com/ztow/zw-photo-organizer.git ~/.openclaw/skills/zw-photo-organizer

# 安装依赖
pip3 install Pillow --break-system-packages

# 配置 OpenClaw（可选）
# 编辑 ~/.openclaw/openclaw.json 添加：
# {
#   "skills": {
#     "zw-photo-organizer": {
#       "path": "~/.openclaw/skills/zw-photo-organizer",
#       "command": "/zphoto"
#     }
#   }
# }
```

### 方式三：一键安装脚本

```bash
# 使用安装脚本（推荐 Mac/Linux）
curl -fsSL https://raw.githubusercontent.com/ztow/zw-photo-organizer/main/install.sh | bash

# 或使用 wget
wget -qO- https://raw.githubusercontent.com/ztow/zw-photo-organizer/main/install.sh | bash
```

安装后直接使用：
```bash
zphoto "/path/to/your/photos"
```

### 方式四：OpenClaw 官方安装（未来支持）

```bash
# 未来将通过 OpenClaw 官方安装
openclaw skill install zw-photo-organizer
```

### 方式二：作为 OpenClaw Skill 安装

```bash
# 克隆到 OpenClaw skills 目录
git clone https://github.com/ztow/zw-photo-organizer.git ~/.openclaw/skills/zw-photo-organizer
```

---

## 🚀 使用方法

### 命令行

```bash
# 基本用法
python3 scripts/organize.py "/path/to/your/photos"

# 预览模式（不实际移动文件）
python3 scripts/organize.py "/path/to/your/photos" --dry-run

# 检测重复照片
python3 scripts/detect_duplicate.py "/path/to/your/photos"
```

### OpenClaw 集成

配置 `openclaw.json`:

```json
{
  "skills": {
    "zw-photo-organizer": {
      "command": "/zphoto",
      "script": "~/.openclaw/skills/zw-photo-organizer/scripts/organize.py",
      "description": "智能照片整理"
    }
  }
}
```

然后使用:

```
/zphoto "/Users/weizhao/Pictures/相机导出图片"
```

或自然语言:

```
帮我整理照片
```

---

## 📁 目录结构

整理后的结构：

```
{你的照片目录}/
├── 📁 {年}/
│   └── 📁 {年}_{月}/
│       └── 📁 {年}_{月}_{日}/
│           └── 照片文件
├── 📁 拿不准/              ← 无法确定日期的照片
└── 📄 YYYYMMDD_照片索引.md  ← 自动生成的索引
```

---

## 🔍 日期识别详解

### Level 1: 文件名中的日期

适用于安卓手机导出的照片。

**支持的格式：**
```
IMG_20241003_143022.jpg      → 2024年10月3日
VID_20231125_203015.mp4      → 2023年11月25日
Screenshot_20250115_112233.png
20241225_Christmas_001.jpg   → 2024年12月25日
```

### Level 2: 上级目录中的日期

适用于苹果相册导出的照片。

**支持的格式：**
```
哈尔滨市, 2025年2月12日/     → 2025年2月12日
2024年10月3日/               → 2024年10月3日
2023-11-25/                  → 2023年11月25日
```

### Level 3: EXIF 元数据

读取照片的 `DateTimeOriginal` 字段。

```bash
# 使用 exiftool 查看
exiftool -DateTimeOriginal IMG_3484.JPG
```

### Level 4: 文件修改时间 (mtime)

最后的 fallback 方案。

---

## 📋 索引文件示例

```markdown
# 照片索引

> 生成时间：2026-03-11 22:10:00  
> 源目录：/Users/weizhao/Pictures/相机导出图片  
> 总照片数：26

## 统计概览

| 日期 | 照片数 | 路径 |
|------|--------|------|
| 2024_11_08 | 6 | 2024/2024_11/2024_11_08 |
| 2024_11_09 | 2 | 2024/2024_11/2024_11_09 |
| 2024_12_13 | 18 | 2024/2024_12/2024_12_13 |

## 详细清单

### 2024/2024_11/2024_11_08 (6张)
- 3G9A8421.JPG (来源: mtime)
- 3G9A8424.JPG (来源: mtime)
- ...
```

---

## ⚙️ 配置

编辑 `config/default.json`:

```json
{
  "photo_extensions": [".jpg", ".jpeg", ".png", ".cr2", ".mov", ".mp4"],
  "max_parent_depth": 3,
  "unsure_folder": "拿不准"
}
```

---

## 🛡️ 安全原则

1. **不删除任何照片** - 无论重复、模糊、曝光过度
2. **拿不准的先放一边** - 放入 `拿不准/` 目录
3. **保持原始文件名** - 不修改照片文件本身
4. **原地整理** - 默认在源目录内整理

---

## 📝 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.1.0 | 2026-03-11 | 日期格式优化，月份和日期补零（1→01，8→08） |
| 1.0.0 | 2026-03-11 | 初始版本，支持四级日期识别 |

---

## 🤝 贡献

欢迎提交 Issue 和 PR！

---

## 📄 许可证

MIT License © 2026 ztow

---

*由露娜 AI 助理协助开发*  
*傲娇但靠谱 😤🌙*
