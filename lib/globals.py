"""Module to initializes global setting for the plugin"""

from __future__ import absolute_import, division, unicode_literals
import os
import sys
from urllib.parse import urlencode, urlsplit
import dataclasses
import xbmcaddon
import xbmcvfs
from .loggers import Logger


@dataclasses.dataclass
class PortalConfig:
    """Portal config"""
    mac_cookie: str = None
    portal_url: str = None
    device_id: str = None
    device_id_2: str = None
    signature: str = None
    serial_number: str = None
    portal_base_url: str = None
    server_address: str = None
    alternative_context_path: bool = False


@dataclasses.dataclass
class AddOnConfig:
    """Addon config"""
    url: str = None
    addon_id: str = None
    name: str = None
    handle: str = None
    addon_data_path: str = None
    max_page_limit: int = 2
    max_retries: int = 3
    token_path: str = None
    cache_enabled: bool = True


@dataclasses.dataclass
class TmdbConfig:
    """TMDB metadata config"""
    enabled: bool = False
    api_key: str = None
    language: str = 'de-DE'
    cache_days: int = 30
    use_poster: bool = True
    use_fanart: bool = True
    use_plot: bool = True
    use_rating: bool = True
    use_genres: bool = True


@dataclasses.dataclass
class FilterConfig:
    """Folder filter config"""
    use_keywords: bool = False   # Stichwörter-Filter aktiv
    use_manual: bool = False     # Manuelle Auswahl aktiv (Vorrang vor Stichwörtern)
    keywords: list = dataclasses.field(default_factory=list)


class GlobalVariables:
    """Class initializes global settings used by the plugin"""

    def __init__(self):
        """Init class"""
        self.__addon = xbmcaddon.Addon()
        self.__is_addd_on_first_run = None
        self.addon_config = AddOnConfig()
        self.portal_config = PortalConfig()
        self.tmdb_config = TmdbConfig()
        self.filter_config = FilterConfig()

    def init_globals(self):
        """Init global settings"""
        self.__is_addd_on_first_run = self.__is_addd_on_first_run is None
        self.addon_config.url = sys.argv[0]

        # Static addon info: only needs to be set once per process lifetime
        if self.__is_addd_on_first_run:
            Logger.debug("First run, loading static addon info")
            self.addon_config.addon_id = self.__addon.getAddonInfo('id')
            self.addon_config.name = self.__addon.getAddonInfo('name')
            self.addon_config.addon_data_path = self.__addon.getAddonInfo('path')
            token_path = xbmcvfs.translatePath(self.__addon.getAddonInfo('profile'))
            if not xbmcvfs.exists(token_path):
                xbmcvfs.mkdirs(token_path)
            self.addon_config.token_path = token_path

        # Settings and handle must be refreshed on every call.
        # Kodi can reuse the same Python process across multiple navigations,
        # so reading settings only once causes stale values after the user
        # changes a setting without restarting Kodi.
        self.__addon = xbmcaddon.Addon()
        self.addon_config.handle = int(sys.argv[1])

        # Init loading/cache settings
        load_all_pages = self.__addon.getSetting('load_all_pages') == 'true'
        self.addon_config.max_page_limit = 9999 if load_all_pages else 2
        # cache_enabled defaults to true; only false when explicitly set to 'false'
        self.addon_config.cache_enabled = self.__addon.getSetting('cache_enabled') != 'false'

        # Init Portal settings
        self.portal_config.mac_cookie = 'mac=' + self.__addon.getSetting('mac_address')
        self.portal_config.device_id = self.__addon.getSetting('device_id')
        self.portal_config.device_id_2 = self.__addon.getSetting('device_id_2')
        self.portal_config.signature = self.__addon.getSetting('signature')
        self.portal_config.serial_number = self.__addon.getSetting('serial_number')
        self.portal_config.alternative_context_path = self.__addon.getSetting('alternative_context_path') == 'true'
        self.__set_portal_addresses()

        # Init TMDB settings
        self.tmdb_config.enabled = self.__addon.getSetting('tmdb_enabled') == 'true'
        self.tmdb_config.api_key = self.__addon.getSetting('tmdb_api_key')
        self.tmdb_config.language = self.__addon.getSetting('tmdb_language') or 'de-DE'
        try:
            cache_days = int(self.__addon.getSetting('tmdb_cache_days') or '30')
            # 0 = never delete (spinner option); negative values → clamp to 1
            self.tmdb_config.cache_days = cache_days if cache_days >= 0 else 1
        except (ValueError, TypeError):
            self.tmdb_config.cache_days = 30
        # Default true: only false when explicitly set to 'false'
        self.tmdb_config.use_poster  = self.__addon.getSetting('tmdb_use_poster')  != 'false'
        self.tmdb_config.use_fanart  = self.__addon.getSetting('tmdb_use_fanart')  != 'false'
        self.tmdb_config.use_plot    = self.__addon.getSetting('tmdb_use_plot')    != 'false'
        self.tmdb_config.use_rating  = self.__addon.getSetting('tmdb_use_rating')  != 'false'
        self.tmdb_config.use_genres  = self.__addon.getSetting('tmdb_use_genres')  != 'false'

        # Init Folder Filter settings
        # folder_filter_mode: 0=show all, 1=keyword filter, 2=manual selection
        try:
            filter_mode = int(self.__addon.getSetting('folder_filter_mode') or '0')
        except (ValueError, TypeError):
            filter_mode = 0
        self.filter_config.use_keywords = (filter_mode == 1)
        self.filter_config.use_manual = (filter_mode == 2)
        kw_raw = self.__addon.getSetting('folder_filter_keywords') or ''
        self.filter_config.keywords = [k.strip().lower() for k in kw_raw.split(',') if k.strip()]

    def get_handle(self):
        """Get addon handle"""
        return self.addon_config.handle

    def get_custom_thumb_path(self, thumb_file_name):
        """Get thumb file path"""
        return os.path.join(self.addon_config.addon_data_path, 'resources', 'media', thumb_file_name)

    def get_filter_file_path(self, cat_type):
        """Get path for folder filter selection file (cat_type: vod, series, tv)"""
        return os.path.join(self.addon_config.token_path, 'folder_filter_{}.json'.format(cat_type))

    def get_plugin_url(self, params):
        """Get plugin url"""
        return '{}?{}'.format(self.addon_config.url, urlencode(params))

    def __get_portal_base_url(self):
        """Get portal base url"""
        split_url = urlsplit(self.portal_config.server_address)
        return split_url.scheme + '://' + split_url.netloc

    def __set_portal_addresses(self):
        """Set portal urls"""
        self.portal_config.server_address = self.__addon.getSetting('server_address')
        self.portal_config.portal_base_url = self.__get_portal_base_url()
        self.portal_config.portal_url = self.get_portal_url()

    def get_portal_url(self):
        """Get portal url"""
        context_path = '/portal.php' if self.portal_config.alternative_context_path else '/server/load.php'
        portal_url = self.portal_config.portal_base_url + '/stalker_portal' + context_path
        if self.portal_config.server_address.endswith('/c/'):
            portal_url = self.portal_config.server_address.replace('/c/', '') + context_path
        elif self.portal_config.server_address.endswith('/c'):
            portal_url = self.portal_config.server_address.replace('/c', '') + context_path
        return portal_url


G = GlobalVariables()
