#!/usr/bin/env python3
"""
赵兄的智能照片整理 - 主脚本
支持四级日期识别和自动生成索引
"""

import os
import re
import sys
import shutil
import json
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
                import re
                date_match = re.search(rb'(\d{4}):(\d{2}):(\d{2})', exif_data)
                if date_match:
                    year, month, day = date_match.groups()
                    return f"{year.decode()}_{int(month.decode()):02d}_{int(day.decode()):02d}"
    except Exception as e:
        pass
    return None


def extract_date_from_mtime(file_path):
    """Level 4: 从文件修改时间提取"""
    stat = os.stat(file_path)
    dt = datetime.fromtimestamp(stat.st_mtime)
    return f"{dt.year}_{dt.month:02d}_{dt.day:02d}"


def get_photo_date(file_path, source_root=None):
    """完整日期识别流程，返回 (日期, 来源)"""
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
    
    # Level 4: mtime
    date = extract_date_from_mtime(file_path)
    return date, 'mtime'


def is_photo(file_path):
    """检查是否为照片文件"""
    return Path(file_path).suffix.lower() in {ext.lower() for ext in PHOTO_EXTENSIONS}


def organize_photos(source_dir, dry_run=False):
    """整理照片"""
    source = Path(source_dir).resolve()
    
    if not source.exists():
        print(f"❌ 目录不存在: {source}")
        return False
    
    # 统计
    stats = {
        'total': 0,
        'organized': 0,
        'unsure': 0,
        'by_date': defaultdict(list),
        'by_source': defaultdict(int)
    }
    
    # 创建拿不准目录
    unsure_dir = source / '拿不准'
    if not dry_run:
        unsure_dir.mkdir(exist_ok=True)
    
    print(f"🔍 扫描目录: {source}")
    print(f"{'[预览模式]' if dry_run else ''} 开始整理...\n")
    
    # 收集所有照片
    photos = []
    for file_path in source.rglob('*'):
        if file_path.is_file() and is_photo(file_path):
            # 跳过已整理目录中的文件（检查是否在 年/月/日 结构目录中）
            rel_path = str(file_path.relative_to(source))
            if '拿不准' in rel_path:
                continue
            # 检查是否在 2024/2024_11/2024_11_08 这种结构中
            parts = rel_path.split('/')
            if len(parts) >= 3 and parts[0].isdigit() and len(parts[0]) == 4:
                # 可能是已整理的年/月/日结构，跳过
                continue
            photos.append(file_path)
    
    stats['total'] = len(photos)
    print(f"📸 发现 {len(photos)} 张照片\n")
    
    # 处理每张照片
    for photo_path in photos:
        date, source_type = get_photo_date(photo_path, source_root=source)
        stats['by_source'][source_type] += 1
        
        if not date:
            # 无法识别，放入拿不准
            target = unsure_dir / photo_path.name
            if not dry_run:
                shutil.move(str(photo_path), str(target))
            print(f"  [拿不准] {photo_path.name}")
            stats['unsure'] += 1
            continue
        
        # 解析日期
        year, month, day = date.split('_')
        
        # 创建目录结构
        target_dir = source / year / f"{year}_{month}" / f"{year}_{month}_{day}"
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
        
        # 移动文件
        target = target_dir / photo_path.name
        if not dry_run:
            shutil.move(str(photo_path), str(target))
        
        rel_path = f"{year}/{year}_{month}/{year}_{month}_{day}"
        stats['by_date'][date].append({
            'name': photo_path.name,
            'path': rel_path,
            'source': source_type
        })
        stats['organized'] += 1
        
        print(f"  [{source_type:10}] {photo_path.name} → {rel_path}")
    
    # 生成索引
    if not dry_run and stats['organized'] > 0:
        generate_index(source, stats)
    
    # 打印统计
    print(f"\n{'='*50}")
    print(f"📊 整理完成!")
    print(f"   总计: {stats['total']} 张")
    print(f"   已分类: {stats['organized']} 张")
    print(f"   拿不准: {stats['unsure']} 张")
    print(f"\n📅 日期来源统计:")
    for src, count in sorted(stats['by_source'].items()):
        print(f"   - {src}: {count} 张")
    
    return True


def generate_index(source_dir, stats):
    """生成索引文件"""
    today = datetime.now().strftime('%Y%m%d')
    index_file = source_dir / f"{today}_照片索引.md"
    
    content = f"""# 照片索引

> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
> 源目录：{source_dir}  
> 总照片数：{stats['total']}

## 统计概览

| 日期 | 照片数 | 路径 |
|------|--------|------|
"""
    
    # 按日期排序
    for date in sorted(stats['by_date'].keys()):
        photos = stats['by_date'][date]
        year, month, day = date.split('_')
        path = f"{year}/{year}_{month}/{date}"
        content += f"| {date} | {len(photos)} | {path} |\n"
    
    if stats['unsure'] > 0:
        content += f"| 拿不准 | {stats['unsure']} | 拿不准/ |\n"
    
    content += "\n## 详细清单\n\n"
    
    # 详细清单
    for date in sorted(stats['by_date'].keys()):
        photos = stats['by_date'][date]
        year, month, day = date.split('_')
        path = f"{year}/{year}_{month}/{date}"
        
        content += f"### {path} ({len(photos)}张)\n\n"
        for photo in photos:
            content += f"- {photo['name']} (来源: {photo['source']})\n"
        content += "\n"
    
    # 拿不准
    if stats['unsure'] > 0:
        content += "### 拿不准 ({stats['unsure']}张)\n\n"
        content += "请人工确认这些照片的拍摄日期。\n\n"
    else:
        content += "### 拿不准 (0张)\n\n无\n"
    
    # 写入文件
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n📝 索引已生成: {index_file}")


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
