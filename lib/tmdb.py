"""
TMDB (The Movie Database) client for metadata enrichment.
Uses the TMDB REST API v3 and caches results locally.
Compatible with TMDb Helper addon (sets tmdb unique ID on ListItems).
"""
from __future__ import absolute_import, division, unicode_literals

import json
import os
import time

import requests
import xbmcvfs

from .loggers import Logger

TMDB_API_BASE = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w500'
TMDB_FANART_BASE = 'https://image.tmdb.org/t/p/w1280'
CACHE_EXPIRY_DAYS = 30

# Special keys in the cache dict for genre maps (not real film entries)
_GENRE_KEY_MOVIE = '__genres_movie__'
_GENRE_KEY_TV = '__genres_tv__'

# Sentinel: returned by __from_cache() when the key is not in the cache at all.
# This distinguishes "not found" from "found but TMDB had no result" (None).
_CACHE_MISS = object()


class TmdbRateLimitError(Exception):
    """Raised when TMDB returns HTTP 429 too many times in a row.

    This means TMDB has temporarily blocked requests from this API key.
    The caller should stop the current operation and show the user a message.
    """


class TmdbClient:
    """Client for TMDB API with local disk cache and built-in rate limiting."""

    __CACHE_FILE = 'tmdb_cache.json'

    # Stay safely below TMDB's published limit of 40 requests / 10 seconds
    _RATE_MAX = 35
    _RATE_WINDOW = 10  # seconds

    # Stop and raise TmdbRateLimitError after this many back-to-back 429s
    _MAX_CONSECUTIVE_429 = 3

    def __init__(self, api_key, language='de-DE', cache_days=30):
        self.__api_key = api_key
        self.__language = language
        # 0 = never delete cache; negative values → clamp to 1
        self.__cache_days = int(cache_days) if int(cache_days) >= 0 else 1
        self.__cache_path = None
        self.__cache = {}
        self.__cache_loaded = False
        self._request_times = []   # timestamps of recent requests (rate limiter)
        self._consecutive_429 = 0  # counts 429 responses in a row
        self._aborted = False      # True after rate-limit abort – all calls become no-ops

    def __ensure_cache_path(self):
        """Lazy-load cache path (requires G to be initialized)"""
        if self.__cache_path is None:
            from .globals import G
            self.__cache_path = os.path.join(G.addon_config.token_path, self.__CACHE_FILE)
            self.__cache = self.__load_cache()
            self.__cache_loaded = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_movie_info(self, title, year=None):
        """Search TMDB for a movie. Returns metadata dict or None.

        Raises TmdbRateLimitError if TMDB blocks us repeatedly.
        Returns None immediately (without a network call) once aborted.
        """
        if self._aborted:
            return None
        self.__ensure_cache_path()
        cache_key = self.__make_key(title, year, 'movie')
        cached = self.__from_cache(cache_key)
        if cached is not _CACHE_MISS:
            return cached  # None = negative cache (TMDB had no result), dict = found
        result = self.__search_movie(title, year)
        self.__to_cache(cache_key, result)
        return result

    def get_tv_info(self, title, year=None):
        """Search TMDB for a TV show. Returns metadata dict or None.

        Raises TmdbRateLimitError if TMDB blocks us repeatedly.
        Returns None immediately (without a network call) once aborted.
        """
        if self._aborted:
            return None
        self.__ensure_cache_path()
        cache_key = self.__make_key(title, year, 'tv')
        cached = self.__from_cache(cache_key)
        if cached is not _CACHE_MISS:
            return cached  # None = negative cache (TMDB had no result), dict = found
        result = self.__search_tv(title, year)
        self.__to_cache(cache_key, result)
        return result

    def get_genre_map(self, media_type='movie'):
        """Return a dict {genre_id_str: genre_name} for movies or TV shows.

        Downloads once from TMDB and caches for 30 days.
        media_type: 'movie' or 'tv'
        """
        if self._aborted:
            return {}
        self.__ensure_cache_path()
        cache_key = _GENRE_KEY_MOVIE if media_type == 'movie' else _GENRE_KEY_TV
        cached = self.__from_cache(cache_key)
        if cached is not _CACHE_MISS:
            return cached if cached is not None else {}
        endpoint = '{}/genre/{}/list'.format(TMDB_API_BASE, media_type)
        params = {'api_key': self.__api_key, 'language': self.__language}
        response = self.__get(endpoint, params)
        if response is None:
            return {}
        genres = response.json().get('genres', [])
        genre_map = {str(g['id']): g['name'] for g in genres}
        self.__to_cache(cache_key, genre_map)
        return genre_map

    # ------------------------------------------------------------------
    # Private HTTP with rate limiting and 429 guard
    # ------------------------------------------------------------------

    def __get(self, url, params, timeout=5):
        """Centralized HTTP GET.

        - Throttles to _RATE_MAX requests per _RATE_WINDOW seconds.
        - On HTTP 429: waits Retry-After seconds, then returns None.
        - After _MAX_CONSECUTIVE_429 back-to-back 429s: sets _aborted=True
          and raises TmdbRateLimitError so the caller can stop and inform
          the user.
        - Returns a Response object on success, None on recoverable errors.
        """
        # --- Rate throttle: wait if we're sending too many requests ---
        now = time.time()
        self._request_times = [t for t in self._request_times if now - t < self._RATE_WINDOW]
        if len(self._request_times) >= self._RATE_MAX:
            wait = self._RATE_WINDOW - (now - self._request_times[0]) + 0.1
            if wait > 0:
                Logger.debug('TMDB rate throttle: waiting {:.1f}s'.format(wait))
                time.sleep(wait)

        try:
            response = requests.get(url, params=params, timeout=timeout)
            self._request_times.append(time.time())

            if response.status_code == 200:
                self._consecutive_429 = 0  # success resets the counter
                return response

            if response.status_code == 429:
                self._consecutive_429 += 1
                retry_after = int(response.headers.get('Retry-After', 10))
                retry_after = min(retry_after, 60)  # never wait more than 60 s
                Logger.warn(
                    'TMDB 429 (#{} von max {}): warte {}s'.format(
                        self._consecutive_429, self._MAX_CONSECUTIVE_429, retry_after
                    )
                )
                if self._consecutive_429 >= self._MAX_CONSECUTIVE_429:
                    self._aborted = True
                    raise TmdbRateLimitError(
                        'TMDB hat {} Anfragen nacheinander blockiert (HTTP 429). '
                        'Download abgebrochen.'.format(self._consecutive_429)
                    )
                time.sleep(retry_after)
                return None  # skip this one film, caller continues

            Logger.warn('TMDB HTTP {}: {}'.format(response.status_code, url))
            return None

        except TmdbRateLimitError:
            raise  # always let this propagate to the caller
        except Exception as exc:
            Logger.warn('TMDB Anfrage-Fehler: {}'.format(exc))
            return None

    # ------------------------------------------------------------------
    # Private API calls
    # ------------------------------------------------------------------

    def __search_movie(self, title, year):
        """Call TMDB search/movie endpoint"""
        params = {
            'api_key': self.__api_key,
            'query': title,
            'language': self.__language,
            'include_adult': 'false',
        }
        if year:
            params['year'] = year
        response = self.__get('{}/search/movie'.format(TMDB_API_BASE), params)
        if response is None:
            return None
        results = response.json().get('results', [])
        if results:
            genre_map = self.get_genre_map('movie')
            return self.__parse_movie(results[0], genre_map)
        return None

    def __search_tv(self, title, year):
        """Call TMDB search/tv endpoint"""
        params = {
            'api_key': self.__api_key,
            'query': title,
            'language': self.__language,
        }
        if year:
            params['first_air_date_year'] = year
        response = self.__get('{}/search/tv'.format(TMDB_API_BASE), params)
        if response is None:
            return None
        results = response.json().get('results', [])
        if results:
            genre_map = self.get_genre_map('tv')
            return self.__parse_tv(results[0], genre_map)
        return None

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    @staticmethod
    def __parse_movie(data, genre_map=None):
        """Extract relevant fields from a TMDB movie result"""
        poster = (TMDB_IMAGE_BASE + data['poster_path']) if data.get('poster_path') else None
        fanart = (TMDB_FANART_BASE + data['backdrop_path']) if data.get('backdrop_path') else None
        release = data.get('release_date', '')
        year = int(release[:4]) if release and len(release) >= 4 and release[:4].isdigit() else 0
        genre_map = genre_map or {}
        genres = [genre_map[str(gid)] for gid in data.get('genre_ids', []) if str(gid) in genre_map]
        return {
            'tmdb_id': str(data.get('id', '')),
            'title': data.get('title', ''),
            'plot': data.get('overview', ''),
            'year': year,
            'rating': float(data.get('vote_average', 0)),
            'votes': int(data.get('vote_count', 0)),
            'poster': poster,
            'fanart': fanart,
            'genres': genres,
            'media_type': 'movie',
        }

    @staticmethod
    def __parse_tv(data, genre_map=None):
        """Extract relevant fields from a TMDB TV result"""
        poster = (TMDB_IMAGE_BASE + data['poster_path']) if data.get('poster_path') else None
        fanart = (TMDB_FANART_BASE + data['backdrop_path']) if data.get('backdrop_path') else None
        first_air = data.get('first_air_date', '')
        year = int(first_air[:4]) if first_air and len(first_air) >= 4 and first_air[:4].isdigit() else 0
        genre_map = genre_map or {}
        genres = [genre_map[str(gid)] for gid in data.get('genre_ids', []) if str(gid) in genre_map]
        return {
            'tmdb_id': str(data.get('id', '')),
            'title': data.get('name', ''),
            'plot': data.get('overview', ''),
            'year': year,
            'rating': float(data.get('vote_average', 0)),
            'votes': int(data.get('vote_count', 0)),
            'poster': poster,
            'fanart': fanart,
            'genres': genres,
            'media_type': 'tvshow',
        }

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    @staticmethod
    def __make_key(title, year, media_type):
        """Normalized cache key"""
        return '{}:{}:{}'.format(media_type, title.lower().strip(), str(year) if year else '')

    def __from_cache(self, key):
        """Return cached data if still fresh, else _CACHE_MISS.

        Returns _CACHE_MISS when the key is not in the cache or has expired.
        Returns None when the key IS in the cache but TMDB found no result
        (negative cache) – callers must not trigger a new API call in that case.
        """
        entry = self.__cache.get(key)
        if entry is None:
            return _CACHE_MISS
        if self.__cache_days > 0:
            age_days = (time.time() - entry.get('ts', 0)) / 86400.0
            if age_days >= self.__cache_days:
                return _CACHE_MISS
        # cache_days == 0 → never expire: always return what's stored
        return entry.get('data')  # may itself be None (negative cache)

    def flush(self):
        """Write the in-memory cache to disk once. Call this after processing a full listing.
        This avoids N separate disk writes (one per film) and does a single write instead."""
        if self.__cache_loaded:
            self.__persist_cache()

    def __to_cache(self, key, data):
        """Store data (or None for negative result) in memory only. Call flush() to persist."""
        self.__cache[key] = {'data': data, 'ts': time.time()}

    def __load_cache(self):
        """Load JSON cache from disk"""
        try:
            if xbmcvfs.exists(self.__cache_path):
                with xbmcvfs.File(self.__cache_path, 'r') as fh:
                    content = fh.read()
                    if content:
                        return json.loads(content)
        except Exception as exc:
            Logger.warn('TMDB cache load failed: {}'.format(exc))
        return {}

    def __persist_cache(self):
        """Write cache to disk"""
        try:
            with xbmcvfs.File(self.__cache_path, 'w') as fh:
                fh.write(json.dumps(self.__cache))
        except Exception as exc:
            Logger.warn('TMDB cache save failed: {}'.format(exc))
