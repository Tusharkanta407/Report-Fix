"""Turn Acadza HTML + inline MathML into compact readable text for LLM prompts.

Production HTML is messy: unclosed <span>s, unclosed <mspace>, entities everywhere.
The linear text is only for reading; edits are always validated against the raw HTML.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

VOID_TAGS = {"br", "img", "hr", "input", "meta", "link", "col", "area", "base", "wbr", "source"}
BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "table", "ul", "ol"}
MATH_TOKEN_TAGS = {"mi", "mn", "mo", "mtext", "ms"}


class _Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: dict | None = None, parent: "_Node | None" = None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list = []
        self.parent = parent


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, dict(attrs), self.cur)
        self.cur.children.append(node)
        if tag not in VOID_TAGS:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(_Node(tag, dict(attrs), self.cur))

    def handle_endtag(self, tag):
        node = self.cur
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.cur = node.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def _elements(node: _Node) -> list:
    return [c for c in node.children if isinstance(c, _Node) or (isinstance(c, str) and c.strip())]


def _render(node, in_math: bool = False) -> str:
    if isinstance(node, str):
        if in_math:
            return node.strip()
        return node
    tag = node.tag
    if tag in ("script", "style"):
        return ""
    if tag == "br":
        return "\n"
    if tag == "img":
        return f" [image: {node.attrs.get('src', '')}] "
    if tag == "math":
        inner = "".join(_render(c, True) for c in node.children)
        return f" {inner.strip()} "
    if in_math:
        kids = _elements(node)
        parts = [_render(c, True) for c in kids]
        if tag in MATH_TOKEN_TAGS:
            return "".join(parts)
        if tag == "mfrac" and len(parts) >= 2:
            return f"({parts[0]})/({parts[1]})"
        if tag == "msup" and len(parts) >= 2:
            return f"{parts[0]}^({parts[1]})"
        if tag == "msub" and len(parts) >= 2:
            return f"{parts[0]}_({parts[1]})"
        if tag == "msubsup" and len(parts) >= 3:
            return f"{parts[0]}_({parts[1]})^({parts[2]})"
        if tag == "msqrt":
            return f"sqrt({''.join(parts)})"
        if tag == "mroot" and len(parts) >= 2:
            return f"root[{parts[1]}]({parts[0]})"
        if tag in ("munder", "mover") and len(parts) >= 2:
            return f"{parts[0]}[{parts[1]}]"
        if tag == "munderover" and len(parts) >= 3:
            return f"{parts[0]}[{parts[1]}..{parts[2]}]"
        if tag == "mspace":
            return " " + "".join(parts)
        return "".join(parts)
    inner = "".join(_render(c, False) for c in node.children)
    if tag in BLOCK_TAGS:
        return f"\n{inner}\n"
    return inner


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    text = _render(builder.root)
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def tag_balance(fragment: str) -> int:
    """Net nesting depth a fragment contributes (opens minus closes, void/self-closing ignored)."""
    depth = 0
    for m in re.finditer(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?(/?)>", fragment):
        closing, tag, selfclose = m.group(1), m.group(2).lower(), m.group(3)
        if selfclose or tag in VOID_TAGS:
            continue
        depth += -1 if closing else 1
    return depth


def has_partial_tag(fragment: str) -> bool:
    """True if the fragment cuts through the middle of a tag like `<mi` or `ath>`."""
    lt, gt = fragment.rfind("<"), fragment.rfind(">")
    if lt > gt:
        return True
    first_lt, first_gt = fragment.find("<"), fragment.find(">")
    return first_gt != -1 and (first_lt == -1 or first_gt < first_lt)
