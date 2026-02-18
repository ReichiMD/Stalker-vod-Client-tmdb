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


class TmdbClient:
    """Client for TMDB API with local disk cache"""

    __CACHE_FILE = 'tmdb_cache.json'

    def __init__(self, api_key, language='de-DE'):
        self.__api_key = api_key
        self.__language = language
        self.__cache_path = None
        self.__cache = {}
        self.__cache_loaded = False

    def __ensure_cache_path(self):
        """Lazy-load cache path (requires G to be initialized)"""
        if self.__cache_path is None:
            from .globals import G
            self.__cache_path = os.path.join(G.addon_config.token_path, self.__CACHE_FILE)
            self.__cache = self.__load_cache()
            self.__cache_loaded = True

    def get_movie_info(self, title, year=None):
        """Search TMDB for a movie. Returns metadata dict or None."""
        self.__ensure_cache_path()
        cache_key = self.__make_key(title, year, 'movie')
        cached = self.__from_cache(cache_key)
        if cached is not None:
            return cached
        result = self.__search_movie(title, year)
        self.__to_cache(cache_key, result)
        return result

    def get_tv_info(self, title, year=None):
        """Search TMDB for a TV show. Returns metadata dict or None."""
        self.__ensure_cache_path()
        cache_key = self.__make_key(title, year, 'tv')
        cached = self.__from_cache(cache_key)
        if cached is not None:
            return cached
        result = self.__search_tv(title, year)
        self.__to_cache(cache_key, result)
        return result

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
        try:
            response = requests.get(
                '{}/search/movie'.format(TMDB_API_BASE),
                params=params,
                timeout=10,
            )
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results:
                    return self.__parse_movie(results[0])
            else:
                Logger.warn('TMDB movie search HTTP {}: {}'.format(response.status_code, title))
        except Exception as exc:
            Logger.warn('TMDB movie search exception: {}'.format(exc))
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
        try:
            response = requests.get(
                '{}/search/tv'.format(TMDB_API_BASE),
                params=params,
                timeout=10,
            )
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results:
                    return self.__parse_tv(results[0])
            else:
                Logger.warn('TMDB TV search HTTP {}: {}'.format(response.status_code, title))
        except Exception as exc:
            Logger.warn('TMDB TV search exception: {}'.format(exc))
        return None

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    @staticmethod
    def __parse_movie(data):
        """Extract relevant fields from a TMDB movie result"""
        poster = (TMDB_IMAGE_BASE + data['poster_path']) if data.get('poster_path') else None
        fanart = (TMDB_FANART_BASE + data['backdrop_path']) if data.get('backdrop_path') else None
        release = data.get('release_date', '')
        year = int(release[:4]) if release and len(release) >= 4 and release[:4].isdigit() else 0
        return {
            'tmdb_id': str(data.get('id', '')),
            'title': data.get('title', ''),
            'plot': data.get('overview', ''),
            'year': year,
            'rating': float(data.get('vote_average', 0)),
            'votes': int(data.get('vote_count', 0)),
            'poster': poster,
            'fanart': fanart,
            'media_type': 'movie',
        }

    @staticmethod
    def __parse_tv(data):
        """Extract relevant fields from a TMDB TV result"""
        poster = (TMDB_IMAGE_BASE + data['poster_path']) if data.get('poster_path') else None
        fanart = (TMDB_FANART_BASE + data['backdrop_path']) if data.get('backdrop_path') else None
        first_air = data.get('first_air_date', '')
        year = int(first_air[:4]) if first_air and len(first_air) >= 4 and first_air[:4].isdigit() else 0
        return {
            'tmdb_id': str(data.get('id', '')),
            'title': data.get('name', ''),
            'plot': data.get('overview', ''),
            'year': year,
            'rating': float(data.get('vote_average', 0)),
            'votes': int(data.get('vote_count', 0)),
            'poster': poster,
            'fanart': fanart,
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
        """Return cached data if still fresh, else None"""
        entry = self.__cache.get(key)
        if entry is None:
            return None
        age_days = (time.time() - entry.get('ts', 0)) / 86400.0
        if age_days >= CACHE_EXPIRY_DAYS:
            return None
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
