"""Höflicher Abruf: Bot weist sich aus, prüft robots.txt und hält mindestens 1 Sekunde Abstand pro Host."""
from __future__ import annotations

import time
import urllib.request
import urllib.robotparser
from urllib.parse import urlsplit

USER_AGENT = "VersammlungsradarBot/0.1 (+https://github.com/pietvanbloom-lab/versammlungsradar)"
MIN_INTERVAL = 1.0

_last_hit: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser] = {}


class RobotsDisallowed(Exception):
    pass


def _wait(host: str) -> None:
    gap = time.monotonic() - _last_hit.get(host, 0.0)
    if gap < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - gap)
    _last_hit[host] = time.monotonic()


def _get(url: str, timeout: int = 60) -> bytes:
    _wait(urlsplit(url).netloc)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def allowed(url: str) -> bool:
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(_get(base + "/robots.txt").decode("utf-8", "replace").splitlines())
        _robots[base] = rp
    return _robots[base].can_fetch(USER_AGENT, url)


def fetch(url: str) -> bytes:
    if not allowed(url):
        raise RobotsDisallowed(url)
    return _get(url)
