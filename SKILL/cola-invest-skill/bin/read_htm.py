#!/usr/bin/env python3
"""read_htm - 用 lxml 读取美股 SEC .htm 财报，输出 markdown。

设计原则：准确优先。
- lxml（libxml2 后端）保留完整 DOM 树，能精确抽取 <table> 表格（正确处理
  colspan/rowspan 合并单元格）；针对 SEC 年报（章节标题多包在加粗 <div>/<span>
  内、几乎不用 <h1>-<h4>）额外识别 font-weight:bold 与 "PART I..IV"/"ITEM N"
  模式还原章节层级，而非像 PyMuPDF 那样把 HTML 当"打印预览"渲染成假分页、丢失结构。
- HTML 本身是 Unicode（SEC 年报为 UTF-8），中文无 PDF 的 CID/ToUnicode 乱码问题。
- 不调 LLM、不调 docling，纯本地解析，依赖 bin/.venv 中的 lxml。

用法：
    bin/.venv/bin/python bin/read_htm.py <file.htm>            # 打印 markdown 到 stdout
    bin/.venv/bin/python bin/read_htm.py <file.htm> --out x.md  # 落盘同名 .md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from lxml import html as LH

# 解析时应剔除的标签（无正文价值）
_NOISE_TAGS = frozenset({"script", "style", "noscript", "svg", "iframe", "head", "meta", "link"})
# 轻量噪音选区：这些语义标签多为导航/页眉页脚，财报正文通常不需要
_NAV_TAGS = frozenset({"nav", "header", "footer"})
# iXBRL 元数据头：SEC 文档顶部 <ix:header> 含隐藏维度定义/context/unit 等，全部是
# 无正文价值的 XBRL 元数据（CIK、表单类型、会计期间等），需整段剔除。
# 注意：正文表格里的内联 <ix:nonnumeric>/<ix:nonfraction> 是带 XBRL 标注的正文事实，须保留。
_XBRL_NOISE_TAGS = frozenset({"ix:header", "ix:continuation"})
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4"})
_BLOCK_TAGS = frozenset({"p", "div", "blockquote", "section", "article", "pre"})


def _strip_noise(root: "LH.HtmlElement") -> None:
    for tag in (*_NOISE_TAGS, *_NAV_TAGS):
        for el in root.xpath(f"//{tag}"):
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)
    # 剔除 iXBRL 元数据头（含隐藏维度/context/unit 等无正文价值数据）；
    # 用 list() 快照避免在迭代中删节点导致迭代器失效。
    for el in list(root.iter()):
        if isinstance(el.tag, str) and el.tag in _XBRL_NOISE_TAGS:
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)


def _cell_text(cell: "LH.HtmlElement") -> str:
    txt = cell.text_content().strip()
    # 转义 markdown 表格分隔符，合并内部换行
    return txt.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _table_rows(table_el: "LH.HtmlElement"):
    # 兼顾 thead/tbody/tfoot 包裹与裸露 tr
    rows = []
    for sec in table_el.xpath("./*[self::thead or self::tbody or self::tfoot]"):
        rows.extend(sec.xpath("./tr"))
    rows.extend(table_el.xpath("./tr"))
    return rows


def _render_list(node, indent: int = 0) -> str:
    """递归渲染有序/无序列表，保留嵌套层级（子列表缩进）。"""
    items = []
    prefix = "  " * indent + "- "
    for li in node.xpath("./li"):
        parts = []
        if isinstance(li.text, str):
            parts.append(li.text)
        for child in li:
            if child.tag in ("ul", "ol"):
                nested = _render_list(child, indent + 1)
                if nested:
                    items.append(prefix + "".join(parts).strip().replace("\n", " "))
                    items.append(nested)
                    parts = []
                    continue
            else:
                parts.append(_render_node(child))
            if isinstance(child.tail, str):
                parts.append(child.tail)
        line = "".join(parts).strip().replace("\n", " ")
        if line:
            items.append(prefix + line)
    return "\n".join(items)


def _render_table(table_el: "LH.HtmlElement") -> str:
    rows = _table_rows(table_el)
    if not rows:
        return ""
    # 估算列数（按 colspan 累加上界）
    est_cols = 0
    for tr in rows:
        cells = tr.xpath("./*[self::td or self::th]")
        span_sum = sum(int(c.get("colspan", "1") or 1) for c in cells)
        est_cols = max(est_cols, span_sum)
    if est_cols == 0:
        return ""
    n_rows = len(rows)
    occ = [[False] * est_cols for _ in range(n_rows)]
    matrix = [["" for _ in range(est_cols)] for _ in range(n_rows)]

    for r, tr in enumerate(rows):
        cells = tr.xpath("./*[self::td or self::th]")
        c = 0
        for cell in cells:
            while c < est_cols and occ[r][c]:
                c += 1
            if c >= est_cols:
                break
            colspan = max(1, int(cell.get("colspan", "1") or 1))
            rowspan = max(1, int(cell.get("rowspan", "1") or 1))
            text = _cell_text(cell)
            for dr in range(rowspan):
                for dc in range(colspan):
                    rr, cc = r + dr, c + dc
                    if rr < n_rows and cc < est_cols:
                        occ[rr][cc] = True
                        if dr == 0 and dc == 0:
                            matrix[rr][cc] = text
            c += colspan

    # 裁剪全空列
    keep_cols = [c for c in range(est_cols) if any(matrix[r][c].strip() for r in range(n_rows))]
    if not keep_cols:
        return ""
    matrix = [[row[c] for c in keep_cols] for row in matrix]
    est_cols = len(keep_cols)

    # 第一行作表头，其余数据行（markdown 表格需表头行）
    header = matrix[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in range(est_cols)) + " |",
    ]
    for row in matrix[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _render_node_inner(node) -> str:
    """递归渲染节点的内联/块级内容（含 text 与 tail）。

    注意：子结构（表格/标题/列表）渲染出的换行必须保留——只折叠纯文本
    碎片里的多余空白，绝不能把已有的 '\\n' 也当 \\s+ 折叠掉，否则会整篇塌成一行。
    """
    out = []
    if isinstance(node, str):
        return re.sub(r"[ \t]+", " ", node)  # 仅折叠空格/Tab，保留换行
    if node.text:
        out.append(re.sub(r"[ \t]+", " ", node.text))
    for child in node:
        out.append(_render_node(child))
        if isinstance(child.tail, str):
            out.append(re.sub(r"[ \t]+", " ", child.tail))
    return "".join(out)


def _is_bold(el) -> bool:
    """元素是否整体加粗（<b>/<strong> 或 inline style font-weight:bold/700）。"""
    if el.tag in ("b", "strong"):
        return True
    st = (el.get("style") or "").lower().replace(" ", "")
    return "font-weight:bold" in st or "font-weight:700" in st


def _heading_level(text: str) -> int:
    """识别 SEC 年报章节标记：PART I..IV → 1，ITEM N → 2，否则 0。"""
    t = text.strip()
    if not t:
        return 0
    if re.match(r"^PART\s+[IVXLC]+\b", t, re.I):
        return 1
    if re.match(r"^ITEM\s+\d+[A-Z]?\b", t, re.I):
        return 2
    return 0


def _render_node(node) -> str:
    # 文本节点
    if isinstance(node, str):
        return node
    tag = node.tag
    if not isinstance(tag, str):  # 注释 / 处理指令 / DOCTYPE 等非元素节点
        return ""
    if tag in _NOISE_TAGS or tag in _NAV_TAGS:
        return ""
    if tag in ("b", "strong"):
        return "**" + _render_node_inner(node).strip() + "**"
    if tag in ("i", "em"):
        return "*" + _render_node_inner(node).strip() + "*"
    if tag in _HEADING_TAGS:
        level = int(tag[1])
        inner = re.sub(r"[ \t]+", " ", _render_node_inner(node)).strip()
        return "\n\n" + "#" * level + " " + inner + "\n\n"
    if tag == "table":
        return "\n\n" + _render_table(node) + "\n\n"
    if tag in ("ul", "ol"):
        rendered = _render_list(node)
        return "\n" + rendered + "\n" if rendered else ""
    if tag in _BLOCK_TAGS:
        # 保留子结构（表格/标题/列表）生成的换行，只折叠纯文本碎片的多余空格；
        # 并把拼接后的连续空行压成单空行（read_htm 末尾还会再做一次整体折叠）。
        inner = _render_node_inner(node)
        inner = re.sub(r"[ \t]+", " ", inner)
        inner = re.sub(r"\n[ \t]*\n([ \t]*\n)+", "\n\n", inner)
        inner = inner.strip()
        if not inner:
            return ""
        lvl = _heading_level(inner)
        if lvl:
            return "\n\n" + "#" * lvl + " " + inner + "\n\n"
        if _is_bold(node):
            return "\n\n**" + inner + "**\n\n"
        return "\n\n" + inner + "\n\n"
    # 其它标签：递归
    return _render_node_inner(node)


def read_htm(path: "str | Path") -> str:
    """读取 .htm 文件，返回 markdown 字符串。"""
    p = Path(path)
    data = p.read_bytes()
    root = LH.fromstring(data)  # 自动检测编码（含 <meta charset>）
    if root is None:
        raise ValueError(f"无法解析 HTML：{p}")
    _strip_noise(root)
    # 兼容片段（无 <html><body> 包裹）：优先取 body，否则回退到根本身
    body = root.find(".//body")
    if body is None:
        body = root
    md = _render_node(body)
    # 折叠多余空行
    lines = [ln.rstrip() for ln in md.splitlines()]
    cleaned = []
    blank = 0
    for ln in lines:
        if ln.strip() == "":
            blank += 1
            if blank <= 1:
                cleaned.append("")
        else:
            blank = 0
            cleaned.append(ln)
    return "\n".join(cleaned).strip() + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="用 lxml 读取美股 SEC .htm 财报 → markdown")
    parser.add_argument("file", help=".htm 文件路径")
    parser.add_argument("--out", help="落盘 markdown 文件路径（默认打印 stdout）", default=None)
    args = parser.parse_args(argv)

    try:
        md = read_htm(args.file)
    except FileNotFoundError:
        print(f"[read_htm] 文件不存在：{args.file}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[read_htm] 解析失败：{exc}", file=sys.stderr)
        return 1

    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"[read_htm] 已写出：{args.out}（{len(md)} 字符）", file=sys.stderr)
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
