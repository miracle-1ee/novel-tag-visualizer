"""
main.py - 小说标签可视化工具主入口

用法：
  python3 main.py                         # 分析 novels/ 下所有 TXT，输出到 output/
  python3 main.py --novels-dir ./novels   # 指定小说目录
  python3 main.py --output-dir ./output   # 指定输出目录
  python3 main.py --skip-cache            # 忽略缓存，强制重新分析
"""
import sys
import argparse
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="小说标签可视化工具")
    parser.add_argument("--novels-dir", default="novels", help="小说 TXT 目录（默认 novels/）")
    parser.add_argument("--output-dir", default="output", help="图表输出目录（默认 output/）")
    parser.add_argument("--skip-cache", action="store_true", help="忽略缓存，强制重新分析")
    return parser.parse_args()


def check_api_key() -> str:
    """检查 API Key，未配置时给出明确提示"""
    from config import API_KEY
    if not API_KEY:
        print("=" * 60)
        print("❌  未检测到 DeepSeek API Key！")
        print()
        print("请在项目根目录创建 .env 文件，内容如下：")
        print("   DEEPSEEK_API_KEY=你的Key")
        print()
        print("获取 Key：https://platform.deepseek.com/")
        print("=" * 60)
        sys.exit(1)
    return API_KEY


def check_novels_dir(novels_dir: str) -> list:
    """检查小说目录"""
    path = Path(novels_dir)
    if not path.exists():
        print(f"❌  目录不存在：{path.resolve()}")
        print("请创建该目录并放入小说 TXT 文件。")
        sys.exit(1)
    txt_files = list(path.glob("*.txt"))
    if not txt_files:
        print(f"❌  在 {path.resolve()} 中未找到任何 .txt 文件！")
        sys.exit(1)
    return txt_files


def clear_cache_if_needed(skip_cache: bool):
    """--skip-cache 时清空 cache/ 目录"""
    if not skip_cache:
        return
    cache_dir = Path("cache")
    if cache_dir.exists():
        removed = 0
        for f in cache_dir.glob("*.json"):
            f.unlink()
            removed += 1
        if removed:
            print(f"🗑  已清除 {removed} 个缓存文件\n")


def print_summary(result: dict):
    """终端打印分析摘要"""
    total = result.get("total", {})
    dimension_total = result.get("dimension_total", {})

    print()
    print("=" * 60)
    print("📊  标签热度 Top 10")
    print("=" * 60)
    sorted_tags = sorted(total.items(), key=lambda x: x[1], reverse=True)[:10]
    for rank, (tag, score) in enumerate(sorted_tags, 1):
        filled = int(score / max(total.values()) * 20) if total.values() else 0
        bar = "█" * filled + "░" * (20 - filled)
        print(f"  {rank:2d}. {tag:<8}  {bar}  {score}")

    print()
    print("=" * 60)
    print("📐  各维度得分详情")
    print("=" * 60)
    for dim, tag_scores in dimension_total.items():
        dim_total = sum(tag_scores.values())
        top_tag = max(tag_scores, key=tag_scores.get)
        print(f"  {dim}（合计 {dim_total}）  最高：{top_tag}（{tag_scores[top_tag]}）")

    print()


def main():
    print("=" * 60)
    print("     📚  小说标签可视化工具  Novel Tag Visualizer")
    print("=" * 60)

    args = parse_args()

    # 前置检查
    check_api_key()
    txt_files = check_novels_dir(args.novels_dir)
    clear_cache_if_needed(args.skip_cache)

    print(f"\n📂  小说目录：{Path(args.novels_dir).resolve()}")
    print(f"📁  输出目录：{Path(args.output_dir).resolve()}")
    print(f"📚  发现小说：{len(txt_files)} 本\n")
    for f in sorted(txt_files):
        print(f"   • {f.name}")
    print()

    # ===== 第一步：AI 分析 =====
    from analyzer import analyze_all_novels
    result = analyze_all_novels(novels_dir=args.novels_dir)

    if not result:
        print("❌  分析失败，未获得有效结果。请检查 API Key 和小说目录。")
        sys.exit(1)

    # ===== 第二步：可视化 =====
    import visualizer
    visualizer.generate_all(result, output_dir=args.output_dir)

    # ===== 打印摘要 =====
    print_summary(result)

    output_path = Path(args.output_dir).resolve()
    print(f"✅  完成！请查看输出目录：{output_path}")
    print()
    print("  生成的文件：")
    for f in sorted(Path(args.output_dir).glob("*")):
        size_kb = f.stat().st_size / 1024
        print(f"   • {f.name}  ({size_kb:.1f} KB)")
    print("=" * 60)


if __name__ == "__main__":
    main()
