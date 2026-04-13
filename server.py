"""
server.py - Flask 后端
提供：
  GET  /                    — 前端页面
  POST /analyze             — 上传 TXT 文件，返回 SSE 流式进度 + 最终结果图路径
  GET  /output/<filename>   — 获取生成的图片
"""
import os
import json
import time
import shutil
import threading
from pathlib import Path
from flask import Flask, request, Response, send_file, send_from_directory, render_template

app = Flask(__name__)

# Railway / 容器环境用 /tmp，本地用项目目录
_IS_CLOUD = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("PORT")
UPLOAD_DIR = Path("/tmp/uploads") if _IS_CLOUD else Path("uploads")
OUTPUT_DIR = Path("/tmp/output") if _IS_CLOUD else Path("output")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 全局锁，防止并发分析
_analysis_lock = threading.Lock()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/output/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    接收上传的 TXT 文件，以 SSE 流式返回进度和结果。
    SSE 消息格式：
      data: {"type": "log",    "msg": "..."}
      data: {"type": "result", "wordcloud": "/output/wordcloud.png", "bar": "/output/bar_combined.png"}
      data: {"type": "error",  "msg": "..."}
      data: {"type": "done"}
    """
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return Response(
            'data: {"type":"error","msg":"未上传任何文件"}\ndata: {"type":"done"}\n\n',
            content_type="text/event-stream"
        )

    if len(files) > 20:
        return Response(
            'data: {"type":"error","msg":"最多支持 20 个文件"}\ndata: {"type":"done"}\n\n',
            content_type="text/event-stream"
        )

    # 保存上传文件到临时目录
    session_dir = UPLOAD_DIR / f"session_{int(time.time() * 1000)}"
    session_dir.mkdir(parents=True, exist_ok=True)

    saved_count = 0
    for f in files:
        if f.filename and f.filename.lower().endswith(".txt"):
            save_path = session_dir / f.filename
            f.save(str(save_path))
            saved_count += 1

    if saved_count == 0:
        shutil.rmtree(session_dir, ignore_errors=True)
        return Response(
            'data: {"type":"error","msg":"没有有效的 .txt 文件"}\ndata: {"type":"done"}\n\n',
            content_type="text/event-stream"
        )

    def generate():
        try:
            yield sse({"type": "log", "msg": f"已接收 {saved_count} 个文件，开始分析..."})

            from analyzer import analyze_all_novels_stream
            import visualizer

            result = {}
            for msg_type, msg_val in analyze_all_novels_stream(str(session_dir)):
                if msg_type == "log":
                    yield sse({"type": "log", "msg": msg_val})
                elif msg_type == "result":
                    result = msg_val

            if not result or result.get("total") is None:
                yield sse({"type": "error", "msg": "分析结果为空，请检查文件内容或 API Key"})
                yield sse({"type": "done"})
                return

            yield sse({"type": "log", "msg": "\n正在生成可视化图表..."})

            visualizer.plot_wordcloud(result["total"], OUTPUT_DIR)
            yield sse({"type": "log", "msg": "  词云图生成完成 ✓"})

            visualizer.plot_bar_combined(result["total"], OUTPUT_DIR)
            yield sse({"type": "log", "msg": "  合并柱状图生成完成 ✓"})

            visualizer.save_json(result, OUTPUT_DIR)

            yield sse({
                "type": "result",
                "wordcloud": f"/output/wordcloud.png?t={int(time.time())}",
                "bar":       f"/output/bar_combined.png?t={int(time.time())}",
            })
            yield sse({"type": "log", "msg": "\n✅ 全部完成！"})

        except Exception as e:
            import traceback
            yield sse({"type": "error", "msg": f"分析过程出错: {e}\n{traceback.format_exc()}"})
        finally:
            shutil.rmtree(session_dir, ignore_errors=True)
            yield sse({"type": "done"})

    return Response(generate(), content_type="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


if __name__ == "__main__":
    print("=" * 50)
    print("  小说标签可视化工具  已启动")
    print("  访问：http://localhost:5001")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
