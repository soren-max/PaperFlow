from __future__ import annotations

import json
import subprocess
import sys


class ZoteroUnavailable(RuntimeError):
    pass


LIBRARY_SCRIPT = r"""
var search = new Zotero.Search();
search.libraryID = Zotero.Libraries.userLibraryID;
search.addCondition('itemType', 'isNot', 'attachment');
search.addCondition('itemType', 'isNot', 'note');
var ids = await search.search();
var items = (await Zotero.Items.getAsync(ids)).filter(function (item) { return item.isRegularItem(); });
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
return output;
"""


def _zot_command() -> list[str]:
    return [sys.executable, "-m", "zotero_agent"]


def fetch_library(timeout: int = 180) -> list[dict]:
    try:
        result = subprocess.run(
            [*_zot_command(), "exec", "-"],
            input=LIBRARY_SCRIPT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ZoteroUnavailable(f"Could not run zotero-agent: {error}") from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ZoteroUnavailable(detail.removeprefix("error: ") or "Zotero is unavailable")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ZoteroUnavailable("zotero-agent returned an unreadable response") from error
    if not isinstance(payload, list):
        raise ZoteroUnavailable("zotero-agent returned an unexpected response")
    return payload


def ping(timeout: int = 12) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [*_zot_command(), "ping", "--quiet"],
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)
    detail = (result.stderr or result.stdout).strip()
    return result.returncode == 0, detail
