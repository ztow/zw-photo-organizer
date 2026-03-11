#!/usr/bin/env python3
"""
重复照片检测工具
"""

import os
import sys
import hashlib
from pathlib import Path
from collections import defaultdict

PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.cr2', '.nef', '.arw', '.heic', '.mov', '.mp4'}


def get_file_hash(file_path, block_size=65536):
    """计算文件 MD5 哈希"""
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(block_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"  无法读取文件: {file_path} - {e}")
        return None


def find_duplicates(directory):
    """查找重复照片"""
    source = Path(directory).resolve()
    
    if not source.exists():
        print(f"❌ 目录不存在: {source}")
        return
    
    print(f"🔍 扫描目录: {source}\n")
    
    # 收集所有照片
    photos = []
    for file_path in source.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in PHOTO_EXTENSIONS:
            photos.append(file_path)
    
    print(f"📸 发现 {len(photos)} 张照片\n")
    
    # 按文件名分组（可能是同一照片的不同格式）
    by_name = defaultdict(list)
    for photo in photos:
        # 去掉扩展名
        name = photo.stem
        by_name[name].append(photo)
    
    # 查找同名文件
    print("=" * 60)
    print("📋 同名文件（可能是 RAW+JPG 对）:")
    print("=" * 60)
    
    found_pairs = 0
    for name, files in sorted(by_name.items()):
        if len(files) > 1:
            print(f"\n{name}:")
            for f in files:
                size = f.stat().st_size / (1024 * 1024)  # MB
                print(f"  - {f.name} ({size:.1f} MB)")
            found_pairs += 1
    
    if found_pairs == 0:
        print("  未发现同名文件")
    
    # 按文件大小分组（可能是重复文件）
    print("\n" + "=" * 60)
    print("📋 相同大小的文件（可能是重复）:")
    print("=" * 60)
    
    by_size = defaultdict(list)
    for photo in photos:
        size = photo.stat().st_size
        by_size[size].append(photo)
    
    found_dups = 0
    for size, files in sorted(by_size.items()):
        if len(files) > 1:
            # 计算哈希确认是否真重复
            hashes = defaultdict(list)
            for f in files:
                h = get_file_hash(f)
                if h:
                    hashes[h].append(f)
            
            for h, dup_files in hashes.items():
                if len(dup_files) > 1:
                    print(f"\n[重复] 大小: {size / 1024:.1f} KB, 哈希: {h[:16]}...")
                    for f in dup_files:
                        print(f"  - {f}")
                    found_dups += 1
    
    if found_dups == 0:
        print("  未发现重复文件")
    
    print("\n" + "=" * 60)
    print(f"📊 检测完成: 发现 {found_pairs} 组同名文件, {found_dups} 组重复文件")


def main():
    if len(sys.argv) < 2:
        print("用法: python detect_duplicate.py <目录路径>")
        print("示例: python detect_duplicate.py '/Users/weizhao/Pictures/相机导出图片'")
        sys.exit(1)
    
    directory = sys.argv[1]
    find_duplicates(directory)


if __name__ == '__main__':
    main()
