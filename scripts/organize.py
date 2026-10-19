#!/usr/bin/env python3
"""
赵兄的智能照片整理 - 主脚本（v2.1.0 复制式整理）
三级日期识别（文件名 → 上级目录 → EXIF），复制归档到「整理后照片/年/年月」
（按月归档，不按日分目录），原始文件一律不动，生成 Markdown + JSON 双台账。
不用 mtime：文件修改时间不可靠（可能是复制时间，也可能被其它操作改动）。
"""

import os
import re
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from PIL import Image
from PIL.ExifTags import TAGS

# 尝试导入 HEIF 支持
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False

# 照片扩展名（支持大小写）
PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.cr2', '.nef', '.arw', '.heic', '.heif', '.mov', '.mp4',
                    '.JPG', '.JPEG', '.PNG', '.CR2', '.NEF', '.ARW', '.HEIC', '.HEIF', '.MOV', '.MP4'}

TARGET_FOLDER = '整理后照片'
LEDGER_JSON = '整理台账.json'
LEDGER_MD = '整理台账.md'


def extract_date_from_filename(filename):
    """Level 1: 从文件名提取日期"""
    patterns = [
        r'(\d{4})[_-]?(\d{2})[_-]?(\d{2})',  # 20241003, 2024-10-03, 2024_10_03
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            year, month, day = match.groups()
            if 2010 <= int(year) <= 2030 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                return f"{year}_{int(month):02d}_{int(day):02d}"
    return None


def extract_date_from_parent_dirs(file_path, max_depth=3, source_root=None):
    """Level 2: 从上级目录提取日期"""
    file_path = Path(file_path)
    current_dir = file_path.parent

    # 如果文件直接在源目录根目录，跳过
    if source_root and current_dir == Path(source_root):
        return None

    for _ in range(max_depth):
        dir_name = current_dir.name

        # 中文日期：2025年2月12日
        chinese_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', dir_name)
        if chinese_match:
            year, month, day = chinese_match.groups()
            return f"{year}_{int(month):02d}_{int(day):02d}"

        # 标准格式（但排除纯数字如 20260311）
        standard_match = re.search(r'(\d{4})[_-](\d{1,2})[_-](\d{1,2})', dir_name)
        if standard_match:
            year, month, day = standard_match.groups()
            if 2010 <= int(year) <= 2030:
                return f"{year}_{int(month):02d}_{int(day):02d}"

        current_dir = current_dir.parent
        if source_root and current_dir == Path(source_root):
            break
    return None


def extract_date_from_exif(file_path):
    """Level 3: 从 EXIF 提取日期"""
    try:
        image = Image.open(file_path)

        # 尝试获取 EXIF 数据（支持 HEIF）
        exif = None
        if hasattr(image, '_getexif'):
            exif = image._getexif()

        # 标准 EXIF 解析
        if exif:
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal':
                    date_str = value.split(' ')[0]  # 2024:10:03
                    year, month, day = date_str.split(':')
                    return f"{year}_{int(month):02d}_{int(day):02d}"

        # HEIF 格式：从二进制 EXIF 中提取日期
        if hasattr(image, 'info') and 'exif' in image.info:
            exif_data = image.info['exif']
            if isinstance(exif_data, bytes):
                # 在二进制数据中搜索日期格式 YYYY:MM:DD
                date_match = re.search(rb'(\d{4}):(\d{2}):(\d{2})', exif_data)
                if date_match:
                    year, month, day = date_match.groups()
                    return f"{year.decode()}_{int(month.decode()):02d}_{int(day.decode()):02d}"
    except Exception:
        pass
    return None


def get_photo_date(file_path, source_root=None):
    """三级日期识别流程，返回 (日期, 来源)；识别不出返回 (None, None)

    注意：不使用 mtime（文件修改时间）——它可能是复制过去的时间，
    也可能被其它操作改动，不可靠。
    """
    filename = Path(file_path).name

    # Level 1: 文件名
    date = extract_date_from_filename(filename)
    if date:
        return date, 'filename'

    # Level 2: 上级目录
    date = extract_date_from_parent_dirs(file_path, source_root=source_root)
    if date:
        return date, 'parent_dir'

    # Level 3: EXIF
    date = extract_date_from_exif(file_path)
    if date:
        return date, 'exif'

    # 三级都识别不出：拿不准
    return None, None


def is_photo(file_path):
    """检查是否为照片文件"""
    return Path(file_path).suffix.lower() in {ext.lower() for ext in PHOTO_EXTENSIONS}


def collect_photos(source):
    """收集待整理的照片，跳过「整理后照片」目录和旧版遗留的年/月/日结构"""
    photos = []
    for file_path in source.rglob('*'):
        if not file_path.is_file() or not is_photo(file_path):
            continue
        parts = file_path.relative_to(source).parts
        if TARGET_FOLDER in parts:
            continue
        # 兼容旧版遗留的 年/月/日 已归档结构，跳过
        if len(parts) >= 3 and parts[0].isdigit() and len(parts[0]) == 4:
            continue
        photos.append(file_path)
    return photos


def copy_photo(src, target_dir, dry_run=False):
    """复制照片到目标目录，返回 (目标路径, 是否新复制)

    重名处理：目标已存在且大小一致 → 视为已复制过，跳过；
    大小不一致 → 自动加 _1/_2 后缀，避免覆盖。
    """
    target = target_dir / src.name
    if target.exists():
        if target.stat().st_size == src.stat().st_size:
            return target, False
        stem, suffix = src.stem, src.suffix
        i = 1
        while target.exists():
            target = target_dir / f"{stem}_{i}{suffix}"
            i += 1
    if not dry_run:
        shutil.copy2(str(src), str(target))
    return target, True


def organize_photos(source_dir, dry_run=False):
    """整理照片：复制归档 + 生成台账，原始文件一张不删"""
    source = Path(source_dir).resolve()

    if not source.exists():
        print(f"❌ 目录不存在: {source}")
        return False

    target_root = source / TARGET_FOLDER

    stats = {
        'total': 0,
        'organized': 0,
        'unsure': 0,
        'by_date': defaultdict(list),
        'by_source': defaultdict(int),
    }
    organized_entries = []
    unsure_entries = []

    print(f"🔍 扫描目录: {source}")
    print(f"{'[预览模式]' if dry_run else ''} 开始整理（只复制，原始文件不动）...\n")

    photos = collect_photos(source)
    stats['total'] = len(photos)
    print(f"📸 发现 {len(photos)} 张照片\n")

    for photo_path in photos:
        date, source_type = get_photo_date(photo_path, source_root=source)

        if not date:
            # 拿不准：不复制、不删除，留在原处，记入台账
            unsure_entries.append({'name': photo_path.name, 'source_path': str(photo_path)})
            print(f"  [拿不准    ] {photo_path.name}（留在原处）")
            stats['unsure'] += 1
            continue

        stats['by_source'][source_type] += 1
        year, month, _day = date.split('_')
        target_dir = target_root / year / f"{year}_{month}"
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        target, _ = copy_photo(photo_path, target_dir, dry_run)
        rel_path = f"{TARGET_FOLDER}/{year}/{year}_{month}"
        organized_entries.append({
            'name': photo_path.name,
            'date': date,
            'date_source': source_type,
            'source_path': str(photo_path),
            'target_path': str(target),
        })
        stats['by_date'][date].append({'name': photo_path.name, 'path': rel_path, 'source': source_type})
        stats['organized'] += 1
        print(f"  [{source_type:10}] {photo_path.name} → {rel_path}")

    # 生成台账
    if not dry_run:
        write_ledger(source, target_root, stats, organized_entries, unsure_entries)

    # 打印统计
    print(f"\n{'='*50}")
    print(f"📊 整理完成!（复制式，原始文件未动）")
    print(f"   总计: {stats['total']} 张")
    print(f"   已整理（复制）: {stats['organized']} 张")
    print(f"   拿不准（留原处）: {stats['unsure']} 张")
    print(f"\n📅 日期来源统计:")
    for src, count in sorted(stats['by_source'].items()):
        print(f"   - {src}: {count} 张")

    if not dry_run:
        print(f"\n📒 台账已生成: {source / LEDGER_MD}")
        print(f"                {source / LEDGER_JSON}")
        print(f"👉 核对「{TARGET_FOLDER}」无误后，删除已整理的原始文件:")
        print(f"   python3 scripts/clean_organized.py \"{source}\"            # 先预览")
        print(f"   python3 scripts/clean_organized.py \"{source}\" --execute   # 确认后执行")

    return True


def write_ledger(source, target_root, stats, organized_entries, unsure_entries):
    """生成 Markdown + JSON 双台账（同名覆盖上一次）"""
    now = datetime.now()

    ledger = {
        'generated_at': now.strftime('%Y-%m-%d %H:%M:%S'),
        'source_dir': str(source),
        'target_dir': str(target_root),
        'organized': organized_entries,
        'unsure': unsure_entries,
    }
    with open(source / LEDGER_JSON, 'w', encoding='utf-8') as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)

    content = f"""# 整理台账

> 生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}
> 源目录：{source}
> 目标目录：{target_root}
> 已整理（复制）: {stats['organized']} 张；拿不准（留在原处）: {stats['unsure']} 张

## 统计概览

| 日期 | 照片数 | 路径 |
|------|--------|------|
"""
    for date in sorted(stats['by_date'].keys()):
        photos = stats['by_date'][date]
        year, month, _day = date.split('_')
        path = f"{TARGET_FOLDER}/{year}/{year}_{month}"
        content += f"| {date} | {len(photos)} | {path} |\n"

    content += "\n## 已整理清单\n\n"
    content += "| 日期 | 日期来源 | 文件 | 源路径 | 目标路径 |\n"
    content += "|------|----------|------|--------|----------|\n"
    for e in organized_entries:
        content += f"| {e['date']} | {e['date_source']} | {e['name']} | {e['source_path']} | {e['target_path']} |\n"
    if not organized_entries:
        content += "| （无） |  |  |  |  |\n"

    content += f"\n## 拿不准（未复制，留在原处，共 {stats['unsure']} 张）\n\n"
    if unsure_entries:
        for e in unsure_entries:
            content += f"- {e['source_path']}\n"
    else:
        content += "无\n"

    content += f"""
## 下一步

1. 打开「{TARGET_FOLDER}」目录，核对归类是否正确
2. 确认无误后，删除已整理的原始文件（拿不准的一律保留）：

```bash
python3 scripts/clean_organized.py "{source}"            # 先预览
python3 scripts/clean_organized.py "{source}" --execute   # 确认后执行
```
"""
    with open(source / LEDGER_MD, 'w', encoding='utf-8') as f:
        f.write(content)


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python organize.py <目录路径> [--dry-run]")
        print("示例: python organize.py '/Users/weizhao/Pictures/相机导出图片'")
        sys.exit(1)

    source_dir = sys.argv[1]
    dry_run = '--dry-run' in sys.argv

    organize_photos(source_dir, dry_run)


if __name__ == '__main__':
    main()
