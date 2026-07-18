"""CivicClerk, read defensively — portals differ, fields drift.

The API is OData-ish (`/v1/Events?$filter=…`), but tenants disagree about
where the recording URL hides. `parse_events` therefore harvests every
URL-shaped string in each event, keeps the ones that look like video
(Zoom / YouTube / Vimeo / direct files), and shows its work: each event
carries the raw field names the links came from.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional

DEFAULT_TENANT = "brooklinema"

_URL = re.compile(r"https?://[^\s\"'<>\\]+", re.I)
_VIDEOISH = re.compile(
    r"(zoom\.us|zoomgov\.com|youtube\.com|youtu\.be|vimeo\.com|cablecast|"
    r"\.mp4|\.m3u8|\.mov|/video|swagit|granicus|viebit)", re.I)


def events_url(tenant: str, date_from: str, date_to: str, top: int = 100) -> str:
    """OData query for events in [date_from, date_to] (YYYY-MM-DD)."""
    tenant = re.sub(r"[^a-z0-9-]", "", (tenant or DEFAULT_TENANT).lower())
    flt = (f"startDateTime ge {date_from}T00:00:00Z and "
           f"startDateTime le {date_to}T23:59:59Z")
    return (f"https://{tenant}.api.civicclerk.com/v1/Events?"
            f"$filter={flt.replace(' ', '%20')}"
            f"&$orderby=startDateTime%20desc&$top={top}")


def _walk_urls(obj, path="", found=None) -> List[tuple]:
    """Every (field.path, url) anywhere in the event JSON."""
    if found is None:
        found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            _walk_urls(v, f"{path}.{k}" if path else str(k), found)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_urls(v, f"{path}[{i}]", found)
    elif isinstance(obj, str):
        for m in _URL.finditer(obj):
            found.append((path, m.group(0).rstrip(").,;")))
    return found


def _first(d: dict, *names) -> Optional[str]:
    lower = {k.lower(): v for k, v in d.items() if v not in (None, "")}
    for n in names:
        if n.lower() in lower:
            return str(lower[n.lower()])
    return None


def file_stream_url(tenant: str, file_id) -> str:
    """The portal's own file-stream endpoint — answers a GET with the PDF
    bytes (verified live against brooklinema; HEAD gets a 405, that's them)."""
    tenant = re.sub(r"[^a-z0-9-]", "", (tenant or DEFAULT_TENANT).lower())
    return (f"https://{tenant}.api.civicclerk.com/v1/Meetings/"
            f"GetMeetingFileStream(fileId={int(file_id)},plainText=false)")


def event_files(ev: dict, tenant: str = "") -> List[dict]:
    """publishedFiles, read defensively: the portal's typed documents
    (Agenda, Agenda Packet, Minutes…). Their `url` field is a relative
    blob path — the real bytes come from file_stream_url when a tenant
    is known."""
    out = []
    files = ev.get("publishedFiles") or []
    if not isinstance(files, list):
        return out
    for f in files:
        if not isinstance(f, dict):
            continue
        fid = f.get("fileId")
        if not isinstance(fid, (int, float)) and not (
                isinstance(fid, str) and fid.isdigit()):
            continue
        out.append({
            "fileId": int(fid),
            "type": str(f.get("type") or "Document"),
            "name": str(f.get("name") or f.get("type") or "document"),
            "published": str(f.get("publishOn") or ""),
            "url": file_stream_url(tenant, fid) if tenant else "",
        })
    return out


def parse_events(data: dict, tenant: str = "") -> List[dict]:
    """API payload -> [{id, name, category, when, links:[…], files:[…]}].
    `files` carries the typed publishedFiles (agendas, minutes) with real
    stream URLs when a tenant is named; older callers that don't pass one
    still get the link harvest unchanged."""
    rows = data.get("value") if isinstance(data, dict) else None
    if rows is None:
        rows = data if isinstance(data, list) else []
    events = []
    for ev in rows:
        if not isinstance(ev, dict):
            continue
        links = [{"field": f, "url": u, "videoish": bool(_VIDEOISH.search(u))}
                 for f, u in _walk_urls(ev)]
        # CivicClerk stores a bare YouTube id when the station uploads there
        yt = _first(ev, "youtubeVideoId")
        if yt and re.fullmatch(r"[\w-]{6,20}", yt):
            links.append({"field": "youtubeVideoId",
                          "url": f"https://www.youtube.com/watch?v={yt}",
                          "videoish": True})
        seen, uniq = set(), []
        for l in links:
            if l["url"] not in seen:
                seen.add(l["url"])
                uniq.append(l)
        uniq.sort(key=lambda l: not l["videoish"])
        events.append({
            "id": _first(ev, "id", "eventId"),
            "name": _first(ev, "eventName", "name", "title") or "(untitled event)",
            "category": _first(ev, "categoryName", "category", "eventTypeName") or "",
            "when": _first(ev, "startDateTime", "eventDate", "date") or "",
            "links": uniq,
            "files": event_files(ev, tenant),
        })
    return events


def search_events(tenant: str, date_from: str, date_to: str,
                  timeout: float = 15.0) -> List[dict]:
    """Query the portal. Network errors surface as sentences."""
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    url = events_url(tenant, date_from, date_to)
    req = Request(url, headers={"User-Agent": "control-z-grabber",
                                "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        raise RuntimeError(
            f"the {tenant} portal answered {e.code} — check the tenant name "
            f"(it's the part before .api.civicclerk.com)") from e
    except URLError as e:
        raise RuntimeError(
            f"couldn't reach {tenant}.api.civicclerk.com — offline, or not a "
            f"CivicClerk tenant ({getattr(e, 'reason', e)})") from e
    except ValueError as e:
        raise RuntimeError("the portal answered, but not with JSON — "
                           "probably not a CivicClerk tenant") from e
    return parse_events(data, tenant=tenant)
