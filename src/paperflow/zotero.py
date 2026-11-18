from __future__ import annotations

import contextvars
import http.client
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit

from .config import DEFAULT_LOCAL_API_URL, Config

_BACKEND: contextvars.ContextVar[str] = contextvars.ContextVar("paperflow_zotero_backend", default="auto")
_LOCAL_API_URL: contextvars.ContextVar[str] = contextvars.ContextVar(
    "paperflow_zotero_local_api_url",
    default="",
)


@contextmanager
def zotero_context(config: Config):
    """Scope Zotero backend and Local API URL for a command without changing call signatures."""
    token_backend = _BACKEND.set(config.zotero_backend)
    token_url = _LOCAL_API_URL.set(config.zotero_local_api_url)
    try:
        yield
    finally:
        _BACKEND.reset(token_backend)
        _LOCAL_API_URL.reset(token_url)


def _active_backend() -> str:
    return _BACKEND.get()


def _active_local_api_url() -> str:
    return (
        _LOCAL_API_URL.get()
        or os.environ.get("PAPERFLOW_ZOTERO_API_URL")
        or DEFAULT_LOCAL_API_URL
    ).rstrip("/")


class ZoteroUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Collection:
    key: str
    name: str
    parent_key: str | None = None
    item_count: int = 0


COLLECTIONS_SCRIPT = r"""
var collections = Zotero.Collections.getByLibrary(Zotero.Libraries.userLibraryID, true);
return collections.map(function (collection) {
  var parent = collection.parentID ? Zotero.Collections.get(collection.parentID) : null;
  return {
    key: collection.key,
    name: collection.name,
    parent_key: parent ? parent.key : null,
    item_count: collection.getChildItems().filter(function (item) {
      return item.isRegularItem();
    }).length
  };
});
"""


LIBRARY_SCRIPT = r"""
var selectedCollectionKeys = __COLLECTION_KEYS__;
var items;
if (selectedCollectionKeys.length) {
  var seenCollections = {}, collections = [];
  for (var collectionKey of selectedCollectionKeys) {
    var collection = await Zotero.Collections.getByLibraryAndKey(
      Zotero.Libraries.userLibraryID, collectionKey
    );
    if (!collection) return { error: 'collection not found: ' + collectionKey };
    var branch = [collection].concat(
      collection.getDescendents(false, 'collection').map(function (entry) {
        return Zotero.Collections.get(entry.id);
      }).filter(Boolean)
    );
    for (var branchCollection of branch) {
      if (!seenCollections[branchCollection.id]) {
        seenCollections[branchCollection.id] = true;
        collections.push(branchCollection);
      }
    }
  }
  var seenItems = {};
  items = [];
  for (var scopedCollection of collections) {
    for (var scopedItem of scopedCollection.getChildItems()) {
      if (!scopedItem.isRegularItem() || seenItems[scopedItem.id]) continue;
      seenItems[scopedItem.id] = true;
      items.push(scopedItem);
    }
  }
} else {
var search = new Zotero.Search();
search.libraryID = Zotero.Libraries.userLibraryID;
search.addCondition('itemType', 'isNot', 'attachment');
search.addCondition('itemType', 'isNot', 'note');
var ids = await search.search();
items = (await Zotero.Items.getAsync(ids)).filter(function (item) { return item.isRegularItem(); });
}
var output = [];
for (var item of items) {
  var citekey = null;
  try {
    var key = Zotero.BetterBibTeX && Zotero.BetterBibTeX.KeyManager.get(item.id);
    citekey = key ? key.citationKey : null;
  } catch (error) {}
  var annotations = [];
  for (var attachmentID of item.getAttachments()) {
    var attachment = Zotero.Items.get(attachmentID);
    if (!attachment || attachment.attachmentContentType !== 'application/pdf') continue;
    for (var annotation of attachment.getAnnotations()) {
      annotations.push({
        key: annotation.key, type: annotation.annotationType || '',
        page: annotation.annotationPageLabel || '', color: annotation.annotationColor || '',
        text: annotation.annotationText || '', comment: annotation.annotationComment || '',
        sort_index: annotation.annotationSortIndex || ''
      });
    }
  }
  annotations.sort(function (a, b) { return a.sort_index.localeCompare(b.sort_index); });
  output.push({
    zotero_key: item.key, citekey: citekey, item_type: item.itemType,
    title: item.getField('title') || '',
    authors: item.getCreators().map(function (creator) {
      return (creator.firstName ? creator.firstName + ' ' : '') + (creator.lastName || creator.name || '');
    }).filter(Boolean),
    date: item.getField('date') || '',
    venue: item.getField('publicationTitle') || item.getField('bookTitle') ||
      item.getField('publisher') || item.getField('university') || '',
    doi: item.getField('DOI') || '', url: item.getField('url') || '',
    abstract: item.getField('abstractNote') || '',
    tags: item.getTags().map(function (tag) { return tag.tag; }),
    source_modified_at: item.dateModified || '', annotations: annotations
  });
}
var selectedCollections = [];
for (var selectedKey of selectedCollectionKeys) {
  var selectedCollection = await Zotero.Collections.getByLibraryAndKey(
    Zotero.Libraries.userLibraryID, selectedKey
  );
  if (selectedCollection) {
    selectedCollections.push({ key: selectedCollection.key, name: selectedCollection.name });
  }
}
return { items: output, selected_collections: selectedCollections };
"""

PAPER_PDF_SCRIPT = r"""
var item = await Zotero.Items.getByLibraryAndKeyAsync(
  Zotero.Libraries.userLibraryID, __ITEM_KEY__
);
if (!item || !item.isRegularItem()) return { error: 'Zotero item not found' };
var pdfs = [];
for (var attachmentID of item.getAttachments()) {
  var attachment = Zotero.Items.get(attachmentID);
  if (!attachment || attachment.attachmentContentType !== 'application/pdf') continue;
  var path = await attachment.getFilePathAsync();
  if (path) pdfs.push({ key: attachment.key, path: path });
}
return {
  zotero_key: item.key,
  title: item.getField('title') || '',
  abstract: item.getField('abstractNote') || '',
  pdfs: pdfs
};
"""


def _zot_command() -> list[str]:
    return [sys.executable, "-m", "zotero_agent"]


def _run_zot(arguments: list[str], *, input_text: str | None = None, timeout: int = 30) -> str:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    try:
        result = subprocess.run(
            [*_zot_command(), *arguments],
            input=input_text,
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=environment,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ZoteroUnavailable(f"Could not run zotero-agent: {error}") from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ZoteroUnavailable(detail.removeprefix("error: ") or "Zotero is unavailable")
    return result.stdout


def _local_api_request(
    base_url: str, route: str, *, params: dict | None = None, timeout: int = 30
) -> tuple[int, dict[str, str], str]:
    parsed = urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ZoteroUnavailable(f"Invalid Zotero Local API URL: {base_url}")
    path = f"/api/users/0/{route.lstrip('/')}"
    if params:
        separator = "&" if "?" in path else "?"
        path = f"{path}{separator}{urlencode(params)}"
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = conn_cls(parsed.netloc, timeout=timeout)
    try:
        connection.request("GET", path, headers={"Connection": "close"})
        response = connection.getresponse()
        headers = {k.lower(): v for k, v in response.getheaders()}
        body = response.read().decode("utf-8", errors="replace")
        return response.status, headers, body
    except (OSError, http.client.HTTPException) as error:
        raise ZoteroUnavailable(f"Could not reach Zotero Local API ({base_url}): {error}") from error
    finally:
        connection.close()


def _local_api_json(base_url: str, route: str, *, timeout: int = 30) -> object:
    status, _headers, body = _local_api_request(base_url, route, timeout=timeout)
    if status >= 400:
        raise ZoteroUnavailable(f"Zotero Local API returned HTTP {status} for {route}")
    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise ZoteroUnavailable("Zotero Local API returned unreadable JSON") from error


def _local_api_list(base_url: str, route: str, *, timeout: int = 30) -> list[dict]:
    collected: list[dict] = []
    start = 0
    total: int | None = None
    while True:
        status, headers, body = _local_api_request(
            base_url, route, params={"start": start, "limit": 100}, timeout=timeout
        )
        if status >= 400:
            raise ZoteroUnavailable(f"Zotero Local API returned HTTP {status} for {route}")
        try:
            chunk = json.loads(body)
        except json.JSONDecodeError as error:
            raise ZoteroUnavailable("Zotero Local API returned unreadable JSON") from error
        if not isinstance(chunk, list):
            raise ZoteroUnavailable("Zotero Local API returned an unexpected list payload")
        if total is None and headers.get("total-results") is not None:
            try:
                total = int(headers["total-results"])
            except ValueError:
                total = None
        collected.extend(chunk)
        if len(chunk) < 100 or (total is not None and len(collected) >= total):
            break
        start += 100
    return collected


def _extract_extra_citekey(extra: str) -> str | None:
    for pattern in (
        r"(?im)^Citation Key:\s*([^\s]+)\s*$",
        r"(?im)^tex\.citation-key:\s*([^\s]+)\s*$",
    ):
        if match := re.search(pattern, extra or ""):
            return match.group(1).strip()
    return None


def _format_authors(creators: list[dict]) -> list[str]:
    authors: list[str] = []
    for creator in creators:
        first = (creator.get("firstName") or "").strip()
        last = (creator.get("lastName") or creator.get("name") or "").strip()
        name = f"{first} {last}".strip() if first else last
        if name:
            authors.append(name)
    return authors


def _map_local_item(data: dict, annotations: list[dict]) -> dict:
    venue = (
        data.get("publicationTitle")
        or data.get("bookTitle")
        or data.get("proceedingsTitle")
        or data.get("conferenceName")
        or data.get("repository")
        or data.get("publisher")
        or data.get("university")
        or ""
    )
    return {
        "zotero_key": data["key"],
        "citekey": data.get("citationKey") or _extract_extra_citekey(data.get("extra") or "") or None,
        "item_type": data.get("itemType") or "",
        "title": data.get("title") or "",
        "authors": _format_authors(data.get("creators") or []),
        "date": data.get("date") or "",
        "venue": venue,
        "doi": data.get("DOI") or "",
        "url": data.get("url") or "",
        "abstract": data.get("abstractNote") or "",
        "tags": [tag["tag"] for tag in data.get("tags") or [] if tag.get("tag")],
        "source_modified_at": data.get("dateModified") or "",
        "annotations": sorted(annotations, key=lambda entry: entry["sort_index"]),
    }


def _list_collections_local_api(timeout: int = 30) -> list[Collection]:
    entries = _local_api_list(_active_local_api_url(), "collections", timeout=timeout)
    collections = []
    for entry in entries:
        data = entry.get("data", entry)
        meta = entry.get("meta") or {}
        parent = data.get("parentCollection")
        collections.append(
            Collection(
                key=data.get("key", ""),
                name=data.get("name", "Untitled collection"),
                parent_key=parent if isinstance(parent, str) and parent else None,
                item_count=int(meta.get("numItems") or 0),
            )
        )
    return collections


def _fetch_snapshot_local_api(
    collection_keys: tuple[str, ...] = (), timeout: int = 180
) -> tuple[list[dict], list[Collection]]:
    base_url = _active_local_api_url()
    collections = _list_collections_local_api(timeout=min(timeout, 30))
    by_key = {col.key: col for col in collections}
    selected: list[Collection] = []
    if collection_keys:
        children: dict[str | None, list[str]] = {}
        for col in collections:
            children.setdefault(col.parent_key, []).append(col.key)
        branch_keys: list[str] = []
        seen_cols: set[str] = set()
        for key in collection_keys:
            if key not in by_key:
                raise ZoteroUnavailable(f"collection not found: {key}")
            selected.append(by_key[key])
            stack = [key]
            while stack:
                current = stack.pop()
                if current in seen_cols:
                    continue
                seen_cols.add(current)
                branch_keys.append(current)
                stack.extend(children.get(current, []))
        raw_items: list[dict] = []
        seen_items: set[str] = set()
        for col_key in branch_keys:
            for entry in _local_api_list(
                base_url, f"collections/{col_key}/items/top", timeout=timeout
            ):
                data = entry.get("data", entry)
                item_key = data.get("key")
                if not item_key or item_key in seen_items:
                    continue
                seen_items.add(item_key)
                raw_items.append(data)
    else:
        raw_items = [
            entry.get("data", entry)
            for entry in _local_api_list(base_url, "items/top", timeout=timeout)
        ]

    regular = [
        data
        for data in raw_items
        if data.get("itemType") not in ("attachment", "note", "annotation")
    ]
    annotations_by_item: dict[str, list[dict]] = {}
    if regular:
        annotation_entries = _local_api_list(
            base_url, "items?itemType=annotation", timeout=min(timeout, 60)
        )
        if annotation_entries:
            attachment_entries = _local_api_list(
                base_url, "items?itemType=attachment", timeout=min(timeout, 60)
            )
            attachment_parent = {
                entry.get("data", entry).get("key"): entry.get("data", entry).get("parentItem")
                for entry in attachment_entries
            }
            for entry in annotation_entries:
                ann = entry.get("data", entry)
                parent_item = attachment_parent.get(ann.get("parentItem"))
                if not parent_item:
                    continue
                annotations_by_item.setdefault(parent_item, []).append(
                    {
                        "key": ann.get("key", ""),
                        "type": ann.get("annotationType") or "",
                        "page": ann.get("annotationPageLabel") or "",
                        "color": ann.get("annotationColor") or "",
                        "text": ann.get("annotationText") or "",
                        "comment": ann.get("annotationComment") or "",
                        "sort_index": ann.get("annotationSortIndex") or "",
                    }
                )
    items = [
        _map_local_item(data, annotations_by_item.get(data["key"], [])) for data in regular
    ]
    return items, selected


def _fetch_paper_pdf_local_api(item_key: str, timeout: int = 30) -> dict:
    base_url = _active_local_api_url()
    payload = _local_api_json(base_url, f"items/{item_key}", timeout=timeout)
    if not isinstance(payload, dict):
        raise ZoteroUnavailable("Zotero item not found")
    data = payload.get("data", payload)
    if data.get("itemType") in ("attachment", "note", "annotation"):
        raise ZoteroUnavailable("Zotero item not found")
    children = _local_api_json(base_url, f"items/{item_key}/children", timeout=timeout)
    pdfs: list[dict] = []
    if isinstance(children, list):
        for child in children:
            att = child.get("data", child)
            if att.get("itemType") != "attachment" or att.get("contentType") != "application/pdf":
                continue
            status, _headers, path_text = _local_api_request(
                base_url, f"items/{att['key']}/file/view/url", timeout=timeout
            )
            locator = path_text.strip()
            if status == 200 and locator:
                pdfs.append({"key": att["key"], "path": locator})
    return {
        "zotero_key": data.get("key", item_key),
        "title": data.get("title") or "",
        "abstract": data.get("abstractNote") or "",
        "pdfs": pdfs,
    }


def _ping_local_api(timeout: int = 12) -> tuple[bool, str]:
    try:
        status, _headers, _body = _local_api_request(
            _active_local_api_url(), "collections", params={"limit": 1}, timeout=timeout
        )
    except ZoteroUnavailable as error:
        return False, str(error)
    return status == 200, "local_api" if status == 200 else f"HTTP {status}"


def list_collections(timeout: int = 30) -> list[Collection]:
    backend = _active_backend()
    if backend == "local_api":
        return _list_collections_local_api(timeout=timeout)
    try:
        output = _run_zot(["exec", "-"], input_text=COLLECTIONS_SCRIPT, timeout=timeout)
        payload = json.loads(output)
        if not isinstance(payload, list):
            raise ZoteroUnavailable("zotero-agent returned an unexpected response")
        return [
            Collection(
                key=entry.get("key", ""),
                name=entry.get("name", "Untitled collection"),
                parent_key=entry.get("parent_key") or None,
                item_count=int(entry.get("item_count") or 0),
            )
            for entry in payload
        ]
    except json.JSONDecodeError as error:
        raise ZoteroUnavailable("zotero-agent returned an unreadable response") from error
    except ZoteroUnavailable as bridge_error:
        if backend == "bridge":
            raise
        try:
            return _list_collections_local_api(timeout=timeout)
        except ZoteroUnavailable:
            raise bridge_error from None


def fetch_snapshot(
    collection_keys: tuple[str, ...] = (), timeout: int = 180
) -> tuple[list[dict], list[Collection]]:
    backend = _active_backend()
    if backend == "local_api":
        return _fetch_snapshot_local_api(collection_keys, timeout=timeout)
    try:
        script = LIBRARY_SCRIPT.replace(
            "__COLLECTION_KEYS__", json.dumps(list(collection_keys), ensure_ascii=False)
        )
        output = _run_zot(["exec", "-"], input_text=script, timeout=timeout)
        payload = json.loads(output)
        if not isinstance(payload, dict):
            raise ZoteroUnavailable("zotero-agent returned an unexpected response")
        if payload.get("error"):
            raise ZoteroUnavailable(payload["error"])
        items = payload.get("items")
        if not isinstance(items, list):
            raise ZoteroUnavailable("zotero-agent returned an unexpected response")
        selected = [
            Collection(entry["key"], entry.get("name") or "Untitled collection")
            for entry in payload.get("selected_collections", [])
        ]
        return items, selected
    except json.JSONDecodeError as error:
        raise ZoteroUnavailable("zotero-agent returned an unreadable response") from error
    except ZoteroUnavailable as bridge_error:
        if backend == "bridge":
            raise
        try:
            return _fetch_snapshot_local_api(collection_keys, timeout=timeout)
        except ZoteroUnavailable:
            raise bridge_error from None


def fetch_library(collection_keys: tuple[str, ...] = (), timeout: int = 180) -> list[dict]:
    return fetch_snapshot(collection_keys, timeout)[0]


def fetch_paper_pdf(item_key: str, timeout: int = 30) -> dict:
    """Read one Zotero item and its PDF locators without copying attachments."""
    backend = _active_backend()
    if backend == "local_api":
        return _fetch_paper_pdf_local_api(item_key, timeout=timeout)
    try:
        script = PAPER_PDF_SCRIPT.replace("__ITEM_KEY__", json.dumps(item_key))
        output = _run_zot(["exec", "-"], input_text=script, timeout=timeout)
        payload = json.loads(output)
        if not isinstance(payload, dict):
            raise ZoteroUnavailable("zotero-agent returned an unexpected response")
        if payload.get("error"):
            raise ZoteroUnavailable(payload["error"])
        return payload
    except json.JSONDecodeError as error:
        raise ZoteroUnavailable("zotero-agent returned an unreadable response") from error
    except ZoteroUnavailable as bridge_error:
        if backend == "bridge":
            raise
        try:
            return _fetch_paper_pdf_local_api(item_key, timeout=timeout)
        except ZoteroUnavailable:
            raise bridge_error from None


def ping(timeout: int = 12) -> tuple[bool, str]:
    backend = _active_backend()
    if backend == "local_api":
        return _ping_local_api(timeout=timeout)
    try:
        output = _run_zot(["exec", "-"], input_text="return 1 + 1;", timeout=timeout)
        if output.strip() == "2":
            return True, "bridge"
        bridge_detail = output.strip()
    except ZoteroUnavailable as error:
        bridge_detail = str(error)
    if backend == "bridge":
        return False, bridge_detail
    local_ok, local_detail = _ping_local_api(timeout=timeout)
    if local_ok:
        return True, local_detail
    return False, bridge_detail
