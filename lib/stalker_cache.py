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

    def __init__(self, cache_dir, cache_days=None):
        self._dir = cache_dir
        # cache_days=0 → never expire; None → use default (24h)
        if cache_days is not None and cache_days == 0:
            self._expiry_hours = 0  # never expire
        elif cache_days is not None and cache_days > 0:
            self._expiry_hours = cache_days * 24
        else:
            self._expiry_hours = CACHE_EXPIRY_HOURS

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
    # Portal identity tracking
    # ------------------------------------------------------------------

    @staticmethod
    def check_portal_changed(cache_dir, server, mac):
        """Check if the portal (server+MAC) has changed since the last run.

        Compares the current server/mac with the stored values in
        ``last_portal.json``.  If different, the Stalker cache files are
        deleted (they are portal-specific and useless for a different
        portal).  The TMDB cache is intentionally kept – it is
        title-based and reusable across portals.

        Returns True if a portal change was detected (and cache cleared).
        """
        import glob as globmod
        portal_file = os.path.join(cache_dir, 'last_portal.json')
        current = {'server': server, 'mac': mac}

        # Read previous portal identity
        previous = None
        try:
            if xbmcvfs.exists(portal_file):
                with xbmcvfs.File(portal_file, 'r') as fh:
                    content = fh.read()
                    if content:
                        previous = json.loads(content)
        except Exception:
            previous = None

        # First run or file missing → just store current and return
        if previous is None:
            try:
                with xbmcvfs.File(portal_file, 'w') as fh:
                    fh.write(json.dumps(current))
            except Exception:
                pass
            return False

        # Compare
        if previous.get('server') == server and previous.get('mac') == mac:
            return False  # same portal, nothing to do

        # Portal changed → delete all stalker_*.json files
        Logger.info('Portal changed: {} → {}. Clearing Stalker cache.'.format(
            previous.get('server', '?'), server))
        pattern = os.path.join(cache_dir, 'stalker_*.json')
        for fp in globmod.glob(pattern):
            try:
                xbmcvfs.delete(fp)
            except Exception:
                pass
        # Also delete folder filter selections (portal-specific)
        for ft in ('vod', 'series', 'tv'):
            ff = os.path.join(cache_dir, 'folder_filter_{}.json'.format(ft))
            try:
                if xbmcvfs.exists(ff):
                    xbmcvfs.delete(ff)
            except Exception:
                pass

        # Save new portal identity
        try:
            with xbmcvfs.File(portal_file, 'w') as fh:
                fh.write(json.dumps(current))
        except Exception:
            pass

        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_stale(self, path):
        """True if the cache file is missing or expired."""
        if self._expiry_hours == 0:
            # Never expire – only stale if file is missing
            return not xbmcvfs.exists(path)
        if not xbmcvfs.exists(path):
            return True
        raw = self._read_raw(path)
        if raw is None:
            return True
        age_h = (time.time() - raw.get('ts', 0)) / 3600.0
        return age_h >= self._expiry_hours

    def _read(self, path):
        """Return the data list from a cache file, or None if missing/stale."""
        raw = self._read_raw(path)
        if raw is None:
            return None
        if self._expiry_hours > 0:
            age_h = (time.time() - raw.get('ts', 0)) / 3600.0
            if age_h >= self._expiry_hours:
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
