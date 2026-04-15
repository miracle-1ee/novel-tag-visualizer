"""
analyzer.py - 使用豆包 AI 对小说进行动态标签分析

流程：
1. 分段摘要：将全文分段，每段生成摘要
2. 标签发现：基于摘要，让 AI 自由命名标签并打分（可突破种子标签）
3. 汇总：合并所有书的标签集，形成动态标签集，对缺分的标签补打分

所有进度通过 yield 输出，供前端 SSE 流式展示。
"""
import json
from pathlib import Path
from openai import OpenAI
from config import API_KEY, API_BASE_URL, MODEL_NAME, CHUNK_SIZE, MAX_CHUNKS, SEED_TAG_LIST


# ============================================================
# 文件读取
# ============================================================

def read_novel(filepath: str) -> str:
    for encoding in ["utf-8", "gbk", "utf-8-sig", "gb2312"]:
        try:
            with open(filepath, "r", encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError(f"无法读取文件: {filepath}")


# ============================================================
# 第一步：分段摘要
# ============================================================

def summarize_novel(content: str, book_name: str, client: OpenAI):
    """将小说分段摘要，yield 进度消息，最终 yield ('summary', 摘要文本)"""
    chunks = [content[i: i + CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE)]
    chunks = chunks[:MAX_CHUNKS]
    total = len(chunks)

    yield ("log", f"  [{book_name}] 共 {total} 段，开始逐段摘要...")

    summaries = []
    for idx, chunk in enumerate(chunks):
        yield ("log", f"  [{book_name}] 摘要第 {idx+1}/{total} 段...")
        prompt = (
            f"你是资深网络文学编辑，正在阅读一篇短篇情感故事。\n"
            f"这是第 {idx+1}/{total} 段内容，请用 100~150 字概括核心剧情、人物关系和情感走向。\n"
            f"只输出摘要，不要额外说明。\n\n内容：\n{chunk}"
        )
        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            s = resp.choices[0].message.content.strip()
            summaries.append(f"第{idx+1}段：{s}")
            yield ("log", f"  [{book_name}] 第 {idx+1} 段摘要完成 ✓")
        except Exception as e:
            summaries.append(f"第{idx+1}段：（摘要失败：{e}）")
            yield ("log", f"  [{book_name}] 第 {idx+1} 段摘要失败: {e}")

    yield ("summary", "\n\n".join(summaries))


# ============================================================
# 第二步：动态标签发现 + 打分
# ============================================================

def discover_and_score(book_name: str, summary: str, client: OpenAI):
    """
    让 AI 自由发现标签并打分。
    返回 {标签名: 分数} 字典，AI 可以自行新增种子标签之外的标签。
    yield 进度消息，最终 yield ('scores', dict)
    """
    seed_str = "、".join(SEED_TAG_LIST)
    prompt = f"""你是专业的网络文学分析师，擅长识别情感类故事的题材、情感、剧情和人设特征。

【故事名称】：{book_name}

【全文摘要】：
{summary}

---

请完成以下任务：
1. 基于故事内容，对下列参考标签打分（整数 0~10）
2. 如果你认为故事还有其他鲜明特征，可以**自行新增标签**（用简洁的中文词语，不超过 6 字），并给出分数
3. 每个标签最多打 10 分，每类特征只有 1~3 个标签得高分（7分以上）

参考标签（可新增，不必全部给高分）：{seed_str}

【输出格式】：仅返回 JSON，key 为标签名，value 为整数分值，不要有任何额外文字。

示例：{{"都市言情": 9, "婆媳矛盾": 8, "强势女主": 7, "家庭伦理": 6}}

请输出 JSON："""

    yield ("log", f"  [{book_name}] 正在进行标签分析与打分...")
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=800,
        )
        raw = resp.choices[0].message.content.strip()

        # 提取 JSON
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith("{"):
                    raw = part
                    break

        scores = json.loads(raw)
        # 确保所有值都是合法整数
        cleaned = {}
        for k, v in scores.items():
            try:
                cleaned[str(k).strip()] = max(0, min(10, int(v)))
            except (ValueError, TypeError):
                pass

        yield ("log", f"  [{book_name}] 标签打分完成，共 {len(cleaned)} 个标签 ✓")
        yield ("scores", cleaned)

    except Exception as e:
        yield ("log", f"  [{book_name}] 标签打分失败: {e}")
        yield ("scores", {})


# ============================================================
# 主分析流程（generator，供 server.py 驱动）
# ============================================================

def analyze_all_novels_stream(novels_dir: str = None):
    """
    分析所有小说，全程通过 yield 输出进度。

    yield 类型：
      ("log",    str)          — 进度日志
      ("result", dict)         — 最终结果（分析结束时 yield 一次）

    最终 result 结构：
      {
        "per_book":  { 书名: {标签: 分数}, ... },
        "total":     { 标签: 总分, ... },
        "all_tags":  [所有动态标签列表],
        "book_names": [书名列表],
      }
    """
    if novels_dir is None:
        novels_dir = Path(__file__).parent / "novels"
    else:
        novels_dir = Path(novels_dir)

    txt_files = sorted(novels_dir.glob("*.txt"))
    if not txt_files:
        yield ("log", f"[错误] 在 {novels_dir} 中未找到任何 .txt 文件！")
        yield ("result", {})
        return

    yield ("log", f"发现 {len(txt_files)} 本小说，开始分析...\n")

    client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

    per_book_scores = {}  # { 书名: {标签: 分数} }

    # ===== 逐本分析 =====
    for i, txt_path in enumerate(txt_files):
        book_stem = txt_path.stem
        # 显示名截取前 15 字
        display_name = book_stem[:15] + ("..." if len(book_stem) > 15 else "")

        yield ("log", f"\n[{i+1}/{len(txt_files)}] 《{display_name}》")

        # 检查缓存
        try:
            content = read_novel(str(txt_path))
        except Exception as e:
            yield ("log", f"  读取失败: {e}")
            per_book_scores[book_stem] = {}
            continue

        # 分段摘要
        summary_text = ""
        for msg_type, msg_val in summarize_novel(content, display_name, client):
            if msg_type == "log":
                yield ("log", msg_val)
            elif msg_type == "summary":
                summary_text = msg_val

        if not summary_text:
            yield ("log", f"  [{display_name}] 摘要为空，跳过")
            per_book_scores[book_stem] = {}
            continue

        # 标签发现 + 打分
        scores = {}
        for msg_type, msg_val in discover_and_score(display_name, summary_text, client):
            if msg_type == "log":
                yield ("log", msg_val)
            elif msg_type == "scores":
                scores = msg_val

        per_book_scores[book_stem] = scores

    # ===== 汇总动态标签集 =====
    yield ("log", "\n汇总动态标签集...")

    # 收集所有出现过的标签（分数 > 0 的）
    all_tags_set = set()
    for scores in per_book_scores.values():
        for tag, score in scores.items():
            if score > 0:
                all_tags_set.add(tag)
    all_tags = sorted(all_tags_set)

    # 对每本书补全缺失标签（补 0）
    for book_stem in per_book_scores:
        for tag in all_tags:
            if tag not in per_book_scores[book_stem]:
                per_book_scores[book_stem][tag] = 0

    # 计算总分
    total = {tag: sum(per_book_scores[b].get(tag, 0) for b in per_book_scores) for tag in all_tags}

    yield ("log", f"动态标签集共 {len(all_tags)} 个标签 ✓")
    yield ("log", f"\n✅ 全部 {len(per_book_scores)} 本小说分析完成！")

    yield ("result", {
        "per_book":   per_book_scores,
        "total":      total,
        "all_tags":   all_tags,
        "book_names": list(per_book_scores.keys()),
    })


# ============================================================
# 兼容 main.py 的同步包装
# ============================================================

def analyze_all_novels(novels_dir: str = None) -> dict:
    result = {}
    for msg_type, msg_val in analyze_all_novels_stream(novels_dir):
        if msg_type == "log":
            print(msg_val)
        elif msg_type == "result":
            result = msg_val
    return result
