from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass


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


def list_collections(timeout: int = 30) -> list[Collection]:
    output = _run_zot(["exec", "-"], input_text=COLLECTIONS_SCRIPT, timeout=timeout)
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as error:
        raise ZoteroUnavailable("zotero-agent returned an unreadable response") from error
    if not isinstance(payload, list):
        raise ZoteroUnavailable("zotero-agent returned an unexpected response")
    collections = []
    for entry in payload:
        collections.append(
            Collection(
                key=entry.get("key", ""),
                name=entry.get("name", "Untitled collection"),
                parent_key=entry.get("parent_key") or None,
                item_count=int(entry.get("item_count") or 0),
            )
        )
    return collections


def fetch_snapshot(
    collection_keys: tuple[str, ...] = (), timeout: int = 180
) -> tuple[list[dict], list[Collection]]:
    script = LIBRARY_SCRIPT.replace(
        "__COLLECTION_KEYS__", json.dumps(list(collection_keys), ensure_ascii=False)
    )
    output = _run_zot(["exec", "-"], input_text=script, timeout=timeout)
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as error:
        raise ZoteroUnavailable("zotero-agent returned an unreadable response") from error
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


def fetch_library(collection_keys: tuple[str, ...] = (), timeout: int = 180) -> list[dict]:
    return fetch_snapshot(collection_keys, timeout)[0]


def ping(timeout: int = 12) -> tuple[bool, str]:
    try:
        output = _run_zot(["exec", "-"], input_text="return 1 + 1;", timeout=timeout)
    except ZoteroUnavailable as error:
        return False, str(error)
    return output.strip() == "2", output.strip()
