"""Build a reusable, API-independent UI knowledge graph from DOM records."""
from __future__ import annotations
from collections import defaultdict
from typing import Any
from urllib.parse import urlsplit, urlunsplit

def _stable_url(value: Any, base_url: str) -> str:
    raw = str(value or base_url)
    parts = urlsplit(raw)
    # Discovery must never persist query tokens/fragments as application identity.
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", "", "")) if parts.scheme else raw.split("#", 1)[0].split("?", 1)[0]

def build_ui_graph(elements: list[dict[str, Any]], base_url: str) -> dict[str, Any]:
    pages: dict[str, dict[str, Any]] = defaultdict(lambda: {"elements": [], "routes": []})
    nodes: list[dict[str, Any]] = []
    for index, item in enumerate(elements):
        page = _stable_url(item.get("page_url"), base_url)
        node_id = f"ui-{index:06d}"
        node = {
            "id": node_id,
            "page_url": page,
            "role": item.get("role"),
            "tag": item.get("tag"),
            "name": item.get("name"),
            "label": item.get("label"),
            "attributes": item.get("attributes", {}),
            "locator": {key: item.get(key) for key in (
                "test_id", "element_id", "aria_label", "label", "role",
                "html_name", "placeholder", "visible_text", "css_path"
            ) if item.get(key)},
            "parent": item.get("parent_selector"),
            "parent_id": item.get("parent_id"),
            "children": list(item.get("children", []) or []),
            "frame_url": item.get("frame_url"),
            "shadow_root": bool(item.get("shadow_root")),
        }
        nodes.append(node)
        pages[page]["elements"].append(node_id)
        if item.get("href"):
            pages[page]["routes"].append(_stable_url(item["href"], base_url))
    for page in pages.values():
        page["routes"] = sorted(set(page["routes"]))
    by_parent: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        if node.get("parent_id"):
            by_parent[str(node["parent_id"])].append(node["id"])
    for node in nodes:
        node["children"] = sorted(set(node.get("children", []) + by_parent.get(node["id"], [])))
    return {"version": 2, "base_url": _stable_url(base_url, base_url), "pages": dict(pages), "nodes": nodes}
