#!/usr/bin/env python3
"""
按整理台账清理已整理照片的原始文件。

安全设计：
- 只删台账 organized 里的文件；拿不准（unsure）的一律保留
- 删除前校验目标副本存在、大小一致、MD5 一致（大小相同不代表同一个文件）
- 源文件不存在 / 副本丢失 / 大小不符 / MD5 不符 → 跳过不删
- 默认预览模式，必须显式 --execute 才真正删除
"""

import os
import sys
import json
import hashlib
from pathlib import Path

LEDGER_JSON = '整理台账.json'


def file_md5(path, block_size=65536):
    """计算文件 MD5"""
    hasher = hashlib.md5()
    with open(path, 'rb') as f:
        while chunk := f.read(block_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_ledger(source):
    """加载整理台账（JSON）"""
    ledger_path = source / LEDGER_JSON
    if not ledger_path.exists():
        print(f"❌ 台账不存在: {ledger_path}")
        print("   请先运行 organize.py 完成整理并生成台账。")
        sys.exit(1)
    with open(ledger_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    if len(sys.argv) < 2:
        print("用法: python clean_organized.py <目录路径> [--execute]")
        print("示例: python clean_organized.py '/Users/weizhao/Pictures/相机导出图片'")
        sys.exit(1)

    source = Path(sys.argv[1]).resolve()
    execute = '--execute' in sys.argv

    if not source.exists():
        print(f"❌ 目录不存在: {source}")
        sys.exit(1)

    ledger = load_ledger(source)
    organized = ledger.get('organized', [])
    unsure = ledger.get('unsure', [])

    # 逐条校验，生成待删/跳过两个列表
    to_delete = []
    skipped = []
    for item in organized:
        src = Path(item.get('source_path', ''))
        tgt = Path(item.get('target_path', ''))
        if not src.exists():
            skipped.append((src, '源文件已不存在'))
            continue
        if not tgt.exists():
            skipped.append((src, '目标副本不存在，不删'))
            continue
        if src.stat().st_size != tgt.stat().st_size:
            skipped.append((src, '与副本大小不一致，不删'))
            continue
        if file_md5(src) != file_md5(tgt):
            skipped.append((src, 'MD5 不一致，不删'))
            continue
        to_delete.append(src)

    print(f"📒 台账: {source / LEDGER_JSON}")
    print(f"   生成时间: {ledger.get('generated_at', '未知')}")
    print(f"   已整理: {len(organized)} 条；拿不准: {len(unsure)} 条（一律保留）\n")

    print("=" * 60)
    print(f"🗑️  将删除的原始文件（{len(to_delete)} 个）:")
    print("=" * 60)
    for f in to_delete:
        print(f"  - {f}")
    if not to_delete:
        print("  （无）")

    if skipped:
        print(f"\n⏭️  跳过（{len(skipped)} 个）:")
        for f, reason in skipped:
            print(f"  - {f}（{reason}）")

    print(f"\n🔒 保留：拿不准的 {len(unsure)} 张照片留在原处，不删除。")

    if not execute:
        print(f"\n[预览模式] 未删除任何文件。确认无误后加 --execute 执行:")
        print(f"  python3 clean_organized.py \"{source}\" --execute")
        return

    deleted = 0
    failed = 0
    for f in to_delete:
        try:
            os.remove(f)
            deleted += 1
            print(f"  [已删除] {f}")
        except Exception as e:
            failed += 1
            print(f"  [失败] {f} - {e}")

    print(f"\n{'='*50}")
    print(f"📊 清理完成: 已删除 {deleted} 个，失败 {failed} 个，跳过 {len(skipped)} 个")
    print(f"   拿不准的 {len(unsure)} 张照片已保留在原处")


if __name__ == '__main__':
    main()
