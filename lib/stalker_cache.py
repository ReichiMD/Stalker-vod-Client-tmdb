"""
Local disk cache for Stalker API category and video lists.

One JSON file per entry:
  stalker_cats_vod.json           – list of VOD categories
  stalker_cats_series.json        – list of Series categories
  stalker_videos_vod_<id>.json    – all videos for one VOD category
  stalker_videos_series_<id>.json – all videos for one Series category

Each file format: {"ts": <unix timestamp>, "data": [...]}
Cache expiry: CACHE_EXPIRY_HOURS (default 24 h).
"""
from __future__ import absolute_import, division, unicode_literals

import json
import os
import time

import xbmcvfs

from .loggers import Logger

CACHE_EXPIRY_HOURS = 24


class StalkerCache:
    """Read/write local Stalker API cache for categories and video lists."""

    def __init__(self, cache_dir):
        self._dir = cache_dir

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def get_categories(self, cat_type):
        """Return cached category list or None if missing/stale."""
        return self._read(_cats_path(self._dir, cat_type))

    def set_categories(self, cat_type, categories):
        """Persist category list to disk."""
        self._write(_cats_path(self._dir, cat_type), categories)

    def categories_are_stale(self, cat_type):
        """True if cache file is missing or older than CACHE_EXPIRY_HOURS."""
        return self._is_stale(_cats_path(self._dir, cat_type))

    # ------------------------------------------------------------------
    # Videos per category
    # ------------------------------------------------------------------

    def get_videos(self, cat_type, cat_id):
        """Return cached video list for a category, or None if missing/stale."""
        return self._read(_videos_path(self._dir, cat_type, cat_id))

    def set_videos(self, cat_type, cat_id, videos):
        """Persist video list for a category to disk."""
        self._write(_videos_path(self._dir, cat_type, cat_id), videos)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_stale(self, path):
        """True if the cache file is missing or expired."""
        if not xbmcvfs.exists(path):
            return True
        raw = self._read_raw(path)
        if raw is None:
            return True
        age_h = (time.time() - raw.get('ts', 0)) / 3600.0
        return age_h >= CACHE_EXPIRY_HOURS

    def _read(self, path):
        """Return the data list from a cache file, or None if missing/stale."""
        raw = self._read_raw(path)
        if raw is None:
            return None
        age_h = (time.time() - raw.get('ts', 0)) / 3600.0
        if age_h >= CACHE_EXPIRY_HOURS:
            return None
        return raw.get('data')

    def _read_raw(self, path):
        """Read JSON from path without expiry check. Returns dict or None."""
        try:
            if xbmcvfs.exists(path):
                with xbmcvfs.File(path, 'r') as fh:
                    content = fh.read()
                    if content:
                        return json.loads(content)
        except Exception as exc:  # pylint: disable=broad-except
            Logger.warn('StalkerCache read error {}: {}'.format(path, exc))
        return None

    def _write(self, path, data):
        """Write data list as JSON to path with current timestamp."""
        try:
            with xbmcvfs.File(path, 'w') as fh:
                fh.write(json.dumps({'ts': time.time(), 'data': data}))
        except Exception as exc:  # pylint: disable=broad-except
            Logger.warn('StalkerCache write error {}: {}'.format(path, exc))


# ------------------------------------------------------------------
# Path helpers (module-level for clarity)
# ------------------------------------------------------------------

def _cats_path(cache_dir, cat_type):
    return os.path.join(cache_dir, 'stalker_cats_{}.json'.format(cat_type))


def _videos_path(cache_dir, cat_type, cat_id):
    return os.path.join(cache_dir, 'stalker_videos_{}_{}.json'.format(cat_type, cat_id))
