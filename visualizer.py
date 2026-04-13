"""
visualizer.py - 可视化模块
输出：
  1. wordcloud.png    — 全标签词云
  2. bar_combined.png — 四维度柱状图合并大图（2×2 布局）
"""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")  # 必须在 pyplot 之前设置，兼容多线程/无GUI环境
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path
from wordcloud import WordCloud

# ============================================================
# 中文字体
# ============================================================

def _get_chinese_font():
    candidates = [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode MS.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    for f in fm.findSystemFonts():
        try:
            name = fm.FontProperties(fname=f).get_name()
            if any(kw in name for kw in ["Hei", "Song", "Kai", "Ming", "CJK", "PingFang", "Noto"]):
                return f
        except Exception:
            pass
    return None


FONT_PATH = _get_chinese_font()


def _setup_font():
    if FONT_PATH:
        matplotlib.rcParams["font.family"] = fm.FontProperties(fname=FONT_PATH).get_name()
    else:
        matplotlib.rcParams["font.family"] = ["STHeiti", "SimHei", "WenQuanYi Micro Hei", "sans-serif"]
    matplotlib.rcParams["axes.unicode_minus"] = False


_setup_font()


# ============================================================
# 动态分维度：将 all_tags + total 按种子维度归类，其余归入"其他"
# ============================================================

def _group_tags_by_dimension(total: dict) -> dict:
    """
    将动态标签按种子维度归类。
    不属于任何种子维度的标签归入「其他」维度。
    返回: { 维度名: {标签: 分数}, ... }
    """
    from config import SEED_TAGS
    used = set()
    grouped = {}
    for dim, seeds in SEED_TAGS.items():
        dim_scores = {}
        for tag in seeds:
            if tag in total:
                dim_scores[tag] = total[tag]
                used.add(tag)
        # 同维度 AI 新增的标签（在 total 里但不在任何 seeds 里，按字面匹配不到；
        # 这里改为：AI 新增标签统一归入"其他"）
        if dim_scores:
            grouped[dim] = dim_scores

    # 剩余未归类的标签
    other = {tag: score for tag, score in total.items() if tag not in used and score > 0}
    if other:
        grouped["其他特征"] = other

    return grouped


# ============================================================
# 1. 词云
# ============================================================

def plot_wordcloud(total: dict, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    freq = {k: v for k, v in total.items() if v > 0}
    if not freq:
        print("  [跳过] 词云：所有标签分数均为 0")
        return None

    kwargs = {
        "width": 1400, "height": 700,
        "background_color": "white",
        "max_words": 200,
        "colormap": "plasma",
        "prefer_horizontal": 0.85,
    }
    if FONT_PATH:
        kwargs["font_path"] = FONT_PATH

    wc = WordCloud(**kwargs).generate_from_frequencies(freq)

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title("小说标签热度词云", fontsize=20, fontweight="bold", pad=14)
    plt.tight_layout()

    out = output_dir / "wordcloud.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [词云] → {out}")
    return out


# ============================================================
# 2. 合并柱状图（2×2 布局，最多 4 个维度）
# ============================================================

def plot_bar_combined(total: dict, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    grouped = _group_tags_by_dimension(total)
    if not grouped:
        print("  [跳过] 合并柱状图：无数据")
        return None

    dims = list(grouped.keys())
    n = len(dims)

    # 布局：最多 2 列，行数自动计算
    ncols = min(2, n)
    nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(ncols * 9, nrows * 6),
                             facecolor="#f8f8f8")

    # 统一转为二维列表
    if n == 1:
        axes = [[axes]]
    elif nrows == 1:
        axes = [axes] if ncols == 1 else [list(axes)]
    else:
        axes = [list(row) for row in axes]

    flat_axes = [ax for row in axes for ax in row]

    palette = [
        plt.cm.Set2(np.linspace(0, 1, 8)),
        plt.cm.Set1(np.linspace(0, 1, 8)),
        plt.cm.Pastel2(np.linspace(0, 1, 8)),
        plt.cm.tab20(np.linspace(0, 1, 20)),
    ]

    for i, (dim_name, tag_scores) in enumerate(grouped.items()):
        ax = flat_axes[i]
        ax.set_facecolor("#fdfdfd")

        if not tag_scores or max(tag_scores.values()) == 0:
            ax.text(0.5, 0.5, f"{dim_name}\n（暂无数据）",
                    ha="center", va="center", transform=ax.transAxes, fontsize=14)
            ax.axis("off")
            continue

        # 按分数降序排列
        sorted_pairs = sorted(tag_scores.items(), key=lambda x: x[1])
        tags = [p[0] for p in sorted_pairs]
        scores = [p[1] for p in sorted_pairs]
        colors = palette[i % len(palette)][:len(tags)]

        bars = ax.barh(tags, scores, color=colors, edgecolor="white", height=0.6)

        max_score = max(scores)
        for bar, score in zip(bars, scores):
            if score > 0:
                ax.text(
                    bar.get_width() + max_score * 0.02,
                    bar.get_y() + bar.get_height() / 2,
                    str(score),
                    va="center", ha="left", fontsize=11, fontweight="bold"
                )

        ax.set_xlim(0, max_score * 1.22)
        ax.set_xlabel("10 本小说标签总分", fontsize=11)
        ax.set_title(f"【{dim_name}】", fontsize=14, fontweight="bold", pad=10)
        ax.tick_params(axis="y", labelsize=12)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="x", linestyle="--", alpha=0.4)

    # 隐藏多余的子图
    for j in range(i + 1, len(flat_axes)):
        flat_axes[j].set_visible(False)

    fig.suptitle("小说标签多维度分布", fontsize=18, fontweight="bold", y=1.01)
    plt.tight_layout(pad=2.5)

    out = output_dir / "bar_combined.png"
    plt.savefig(str(out), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [合并柱状图] → {out}")
    return out


# ============================================================
# 3. 保存 JSON
# ============================================================

def save_json(result: dict, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  [JSON] → {out}")
    return out


# ============================================================
# 4. 一键生成
# ============================================================

def generate_all(result: dict, output_dir: str = "output"):
    output_dir = Path(output_dir)
    total = result.get("total", {})

    print("\n生成可视化图表...\n")
    plot_wordcloud(total, output_dir)
    plot_bar_combined(total, output_dir)
    save_json(result, output_dir)
    print(f"\n✅ 图表已保存至：{output_dir.resolve()}\n")
