#!/usr/bin/env python3
"""cola-md2wx: Markdown -> 微信公众平台内联样式 HTML。

仅做文字格式转换（不含图片上传）。公众号后台会过滤 <style>/外链CSS/class/id，
因此所有样式必须写成内联 style。

样式规则（已与用户锁定）：
- h1 / h2 -> 蓝色 #0053E0 + 加粗
- strong  -> 红色 #e60000 + 加粗
- em      -> 原生斜体，不改
- h3-h6 / table / blockquote / pre / code -> 原样透传，不加额外颜色
- 已手动带内联 style 的片段不强求覆盖
"""
import argparse
import sys
from pathlib import Path

import markdown
from bs4 import BeautifulSoup, Tag

HEADER_BLUE = "#0053E0"
STRONG_RED = "#e60000"


def md_to_html(md_text: str) -> str:
    # extra 扩展支持表格、脚注、代码块栅栏等
    raw_html = markdown.markdown(md_text, extensions=["extra"])
    soup = BeautifulSoup(raw_html, "lxml")

    for tag in soup.find_all(["h1", "h2"]):
        _merge_style(tag, f"color:{HEADER_BLUE};font-weight:bold;")

    for tag in soup.find_all("strong"):
        _merge_style(tag, f"color:{STRONG_RED};font-weight:bold;")

    # 清洗：去掉 class / id，公众号不友好
    for tag in soup.find_all(True):
        _ = tag.attrs.pop("class", None)
        _ = tag.attrs.pop("id", None)

    # 移除分隔线（用户不需要）
    for hr in soup.find_all("hr"):
        hr.decompose()

    body = soup.body if soup.body else soup
    return str(body)


def _merge_style(tag: Tag, extra: str) -> None:
    """把 extra 追加到标签已有 style（不覆盖用户已写的样式）。"""
    raw = tag.get("style")
    existing = "" if raw is None else str(raw)
    if existing:
        existing = existing.rstrip(";") + ";"
    tag["style"] = existing + extra


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Markdown -> 微信公众平台内联样式 HTML"
    )
    _ = parser.add_argument("input", help="输入 .md 文件路径")
    _ = parser.add_argument(
        "-o",
        "--output",
        default="output.html",
        help="输出 HTML 路径（默认 output.html）",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[错误] 输入文件不存在: {in_path}", file=sys.stderr)
        return 1

    md_text = in_path.read_text(encoding="utf-8")
    html_body = md_to_html(md_text)

    full_html = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-CN">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        "</head>\n"
        f"{html_body}\n"
        "</html>\n"
    )

    out_path = Path(args.output)
    out_path.write_text(full_html, encoding="utf-8")
    print(f"[完成] 已生成: {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
