# 小说标签可视化工具 · Novel Tag Visualizer

> 使用 DeepSeek AI 对网络小说进行标签分析，并自动生成词云、柱状图、雷达图等可视化图表。

---

## 功能特性

- **AI 智能打分**：调用 DeepSeek API，对小说进行题材、剧情、人设三维度标签打分（0~10 分）
- **结果缓存**：已分析的书籍自动缓存至 `cache/` 目录，避免重复调用 API
- **多种可视化**：
  - 📊 标签词云（`wordcloud.png`）
  - 📊 维度总分柱状图（`dimension_bar.png`）
  - 📊 标签热度 Top 15 排行图（`top_tags_bar.png`）
  - 📊 多书籍维度雷达图（`book_radar.png`）
- **自动编码处理**：支持 UTF-8、GBK、GB2312 等常见编码

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env`，并填入你的 DeepSeek API Key：

```bash
cp .env.example .env
```

编辑 `.env`：

```
DEEPSEEK_API_KEY=你的DeepSeek_API_Key
```

> 获取 API Key：https://platform.deepseek.com/

### 3. 放入小说文件

将小说 `.txt` 文件放入 `novels/` 目录：

```
novels/
  ├── 斗破苍穹.txt
  ├── 诛仙.txt
  └── 凡人修仙传.txt
```

> 支持 UTF-8 和 GBK 编码的 TXT 文件。

### 4. 运行分析

```bash
python main.py
```

可选参数：

```bash
python main.py --novels-dir ./novels --output-dir ./output
```

---

## 输出说明

分析完成后，`output/` 目录会生成以下文件：

| 文件 | 说明 |
|------|------|
| `wordcloud.png` | 标签词云，标签热度越高字体越大 |
| `dimension_bar.png` | 题材/剧情/人设三维度总分横向柱状图 |
| `top_tags_bar.png` | 全部标签热度 Top 15 排行图 |
| `book_radar.png` | 各书籍三维度得分雷达图 |
| `result.json` | 原始分析数据（每本书的全量标签分数） |

---

## 标签体系

分析共涵盖 **3 个维度、45 个标签**：

### 题材维度（15 个）

玄幻、修仙、都市、穿越、末世、科幻、历史、言情、悬疑、武侠、仙侠、奇幻、军事、游戏、竞技

### 剧情维度（15 个）

升级流、系统流、逆袭、复仇、打脸、团宠、宫斗、战争、冒险、种田、无限流、副本、重生、穿书、双洁

### 人设维度（15 个）

腹黑、毒舌、天才、废材逆袭、霸总、白月光、炮灰、学霸、特工、医术、温柔、孤傲、病娇、妹控、强势女主

> 标签可在 `config.py` 中自由修改。

---

## 目录结构

```
novel-tag-visualizer/
├── main.py            # 主入口脚本
├── analyzer.py        # AI 分析模块
├── visualizer.py      # 可视化模块
├── config.py          # 配置（API Key、标签体系）
├── requirements.txt   # Python 依赖
├── .env.example       # API Key 模板
├── .env               # 你的 API Key（不要提交到 git）
├── novels/            # 放入小说 TXT 文件
├── cache/             # 分析结果缓存（自动生成）
└── output/            # 输出图表和 JSON（自动生成）
```

---

## 注意事项

- 每本小说默认只发送前 **8000 字**给 AI 分析（可在 `config.py` 中调整 `MAX_CHARS`）
- 分析结果会缓存在 `cache/` 目录，删除缓存文件可强制重新分析
- `.env` 文件包含 API Key，请勿上传至公开仓库

---

## License

MIT
