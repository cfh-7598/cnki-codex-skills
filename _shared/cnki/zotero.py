"""Zotero integration helpers for CNKI export data."""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ZOTERO_API = "http://127.0.0.1:23119/connector"
HTTP_TIMEOUT = 15


class ZoteroError(RuntimeError):
    """Raised when the local Zotero Connector API fails."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def zotero_request(endpoint: str, data: dict[str, Any] | None = None, timeout: int = HTTP_TIMEOUT):
    url = f"{ZOTERO_API}/{endpoint}"
    body = json.dumps(data or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Zotero-Connector-API-Version": "3",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        text = resp.read().decode("utf-8")
        return resp.status, json.loads(text) if text else None
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(payload) if payload else None
        except json.JSONDecodeError:
            return exc.code, {"error": payload}
    except urllib.error.URLError:
        return 0, None
    except TimeoutError:
        return -1, {"error": f"Timed out after {timeout}s"}


def parse_elearning(text: str) -> dict[str, Any]:
    text = text.replace("<br>", "\n").replace("\r", "")
    text = re.sub(r"<[^>]+>", "", text)

    def get(key: str) -> str:
        match = re.search(rf"{re.escape(key)}:\s*(.+?)(?=\n|$)", text)
        return match.group(1).strip() if match else ""

    return {
        "title": get("Title-题名"),
        "authors": [a.strip() for a in get("Author-作者").split(";") if a.strip()],
        "journal": get("Source-刊名"),
        "year": get("Year-年"),
        "pubTime": get("PubTime-出版时间"),
        "keywords": [k.strip() for k in get("Keyword-关键词").split(";") if k.strip()],
        "abstract": get("Summary-摘要"),
        "volume": get("Roll-卷"),
        "issue": get("Period-期"),
        "pages": get("Page-页码"),
        "link": get("Link-链接"),
    }


def build_zotero_item(paper: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    item = {
        "itemType": "journalArticle",
        "title": paper.get("title", ""),
        "abstractNote": paper.get("abstract", ""),
        "date": paper.get("pubTime") or paper.get("year", ""),
        "language": "zh-CN",
        "libraryCatalog": "CNKI",
        "accessDate": now,
        "volume": paper.get("volume", ""),
        "pages": paper.get("pages", ""),
        "publicationTitle": paper.get("journal", ""),
        "issue": paper.get("issue", ""),
        "creators": [{"name": name, "creatorType": "author"} for name in paper.get("authors", [])],
        "tags": [{"tag": tag, "type": 1} for tag in paper.get("keywords", [])],
        "attachments": [],
    }
    if paper.get("link"):
        item["url"] = paper["link"]
    if paper.get("issn"):
        item["ISSN"] = paper["issn"]
    return item


def save_export_payload_to_zotero(payload: list[dict[str, Any]]) -> dict[str, Any]:
    status, _ = zotero_request("ping")
    if status == 0:
        raise ZoteroError("zotero_unavailable", "Zotero is not running or the Connector API is unavailable.")

    items = []
    for record in payload:
        if "ELEARNING" not in record:
            continue
        parsed = parse_elearning(record["ELEARNING"])
        for key in ("issn", "pageUrl"):
            if record.get(key):
                parsed[key] = record[key]
        items.append(build_zotero_item(parsed))
    if not items:
        raise ZoteroError("not_found", "The CNKI export payload did not include Zotero-ready fields.")

    session_id = hashlib.md5(
        "|".join(sorted(item.get("title", "") for item in items)).encode("utf-8", errors="surrogateescape")
    ).hexdigest()[:12]
    for index, item in enumerate(items):
        item["id"] = f"cnki_{session_id}_{index}"

    status, response = zotero_request("saveItems", {"sessionID": session_id, "uri": payload[0].get("pageUrl", ""), "items": items})
    if status == 201:
        return {"saved": len(items), "session_id": session_id, "already_saved": False}
    if status == 409:
        return {"saved": len(items), "session_id": session_id, "already_saved": True}
    if status == 500:
        detail = response.get("error", "") if response else ""
        raise ZoteroError("zotero_error", f"Zotero returned HTTP 500. {detail}")
    if status == -1:
        raise ZoteroError("zotero_timeout", "Timed out waiting for the Zotero Connector API.")
    raise ZoteroError("zotero_error", f"Unexpected Zotero response: HTTP {status}")

