# -*- coding: utf-8 -*-
""" Background service code """

from __future__ import absolute_import, division, unicode_literals

import json
import os
import threading
from urllib.parse import urlsplit, parse_qsl, urlencode
import requests
import xbmc
import xbmcaddon
import xbmcvfs
from xbmc import Monitor, Player, getInfoLabel
from .loggers import Logger
from .utils import get_int_value, get_next_info_and_send_signal


class BackgroundService(Monitor):
    """ Background service code """

    def __init__(self):
        Monitor.__init__(self)
        self._player = PlayerMonitor()

    def run(self):
        """ Background loop for maintenance tasks """
        Logger.debug('Service started')

        # Give Kodi a few seconds to fully initialize before background tasks
        if self.waitForAbort(5):
            return

        self._check_portal_changed()
        self._check_daily_cache_refresh()

        while not self.abortRequested():
            # Stop when abort requested
            if self.waitForAbort(10):
                break

        Logger.debug('Service stopped')

    def _check_portal_changed(self):
        """Detect portal switch and auto-clear the Stalker cache if needed."""
        addon = xbmcaddon.Addon()
        server = addon.getSetting('server_address')
        mac = addon.getSetting('mac_address')
        if not server or not mac:
            return  # Not configured yet

        profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        from .stalker_cache import StalkerCache
        changed = StalkerCache.check_portal_changed(profile, server, mac)
        if changed:
            import xbmcgui
            xbmcgui.Dialog().ok(
                'Portal gewechselt',
                'Die Portal-Adresse oder MAC-Adresse hat sich geändert.[CR][CR]'
                'Der Portal-Cache wurde automatisch gelöscht.[CR]'
                'TMDB-Daten bleiben erhalten und werden für das '
                'neue Portal wiederverwendet.'
            )

    def _check_daily_cache_refresh(self):
        """Trigger a silent background refresh if the Stalker data cache is stale."""
        addon = xbmcaddon.Addon()
        server = addon.getSetting('server_address')
        mac = addon.getSetting('mac_address')
        if not server or not mac:
            return  # Not configured yet – nothing to refresh
        # Respect cache_enabled setting (default true when not explicitly 'false')
        if addon.getSetting('cache_enabled') == 'false':
            return

        # Read configured cache validity (days); 0 = never delete
        try:
            cache_days = int(addon.getSetting('stalker_cache_days') or '30')
        except (ValueError, TypeError):
            cache_days = 30
        # Migrate old values (1, 3, 7 days) to new default (30 days)
        if cache_days > 0 and cache_days < 30:
            cache_days = 30
        if cache_days == 0:
            return  # Never delete – no automatic refresh

        profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        from .stalker_cache import StalkerCache
        cache = StalkerCache(profile, cache_days=cache_days)
        if cache.categories_are_stale('vod'):
            Logger.debug('Stalker cache stale – triggering silent background refresh')
            xbmc.executebuiltin(
                'RunPlugin(plugin://plugin.video.stalkervod.tmdb/?action=update_new_data&silent=1)'
            )

    def onSettingsChanged(self):  # pylint: disable=invalid-name
        """React to setting changes.
        Action buttons (refresh, update, TMDB, folder filter) are now real
        type="action" buttons in settings.xml and execute directly via RunPlugin.
        No automatic data fetch on first setup – the user should configure
        folder filters first before loading data.
        """
        self._check_portal_changed()


class PlayerMonitor(Player):
    """ A custom Player object with watchdog keepalive for Stalker portals """

    KEEPALIVE_INTERVAL = 30  # seconds between watchdog pings

    def __init__(self):
        """ Initialises a custom Player object """
        self.__listen = False
        self.__av_started = False
        self.__path = None
        self.__keepalive_timer = None
        Player.__init__(self)

    def onPlayBackStarted(self):  # pylint: disable=invalid-name
        """ Will be called when Kodi player starts """
        self.__path = getInfoLabel('Player.FilenameAndPath')
        if not self.__path.startswith('plugin://plugin.video.stalkervod.tmdb/'):
            self.__listen = False
            return
        self.__listen = True
        self.__av_started = False
        Logger.debug('Stalker Player: [onPlayBackStarted] called')

    def onAVStarted(self):  # pylint: disable=invalid-name
        """ Will be called when Kodi has a video or audiostream """
        if not self.__listen:
            return
        Logger.debug('Stalker Player: [onAVStarted] called')
        self.__av_started = True
        self.__start_keepalive()
        params = dict(parse_qsl(urlsplit(self.__path).query))
        episode_no = get_int_value(params, 'series')
        total_episodes = get_int_value(params, 'total_episodes')
        if episode_no != 0 and episode_no < total_episodes:
            params.update({'series': episode_no + 1})
            next_episode_url = '{}?{}'.format('plugin://plugin.video.stalkervod.tmdb/', urlencode(params))
            get_next_info_and_send_signal(params, next_episode_url)

    def onPlayBackError(self):  # pylint: disable=invalid-name
        """ Will be called when playback stops due to an error. """
        if not self.__listen:
            return
        self.__stop_keepalive()
        self.__av_started = False
        self.__listen = False
        Logger.debug('Stalker Player: [onPlayBackError] called')

    def onPlayBackEnded(self):  # pylint: disable=invalid-name
        """ Will be called when [Kodi] stops playing a file """
        if not self.__listen:
            return
        Logger.debug('Stalker Player: [onPlayBackEnded] called')
        self.__stop_keepalive()
        self.__listen = False
        self.__av_started = False

    def onPlayBackStopped(self):  # pylint: disable=invalid-name
        """ Will be called when [user] stops Kodi playing a file """
        if not self.__listen:
            return
        self.__stop_keepalive()
        self.__listen = False
        if not self.__av_started:
            params = dict(parse_qsl(urlsplit(self.__path).query))
            if 'cmd' in params and params.get('use_cmd', '0') == '0':
                Logger.debug('Stalker Player: [onPlayBackStopped] playback failed? retrying with cmd {}'.format(self.__path + "&use_cmd=1"))
                xbmc.executebuiltin("Dialog.Close(all, true)")
                func_str = f'PlayMedia({self.__path + "&use_cmd=1"})'
                xbmc.executebuiltin(func_str)
                return
        self.__av_started = False
        Logger.debug('Stalker Player: [onPlayBackStopped] called')

    # -- Watchdog keepalive --------------------------------------------------

    def __start_keepalive(self):
        """Start periodic watchdog keepalive pings to the Stalker portal."""
        self.__stop_keepalive()
        Logger.debug('Keepalive: starting (interval={}s)'.format(self.KEEPALIVE_INTERVAL))
        self.__keepalive_tick()

    def __stop_keepalive(self):
        """Cancel the keepalive timer."""
        if self.__keepalive_timer is not None:
            self.__keepalive_timer.cancel()
            self.__keepalive_timer = None
            Logger.debug('Keepalive: stopped')

    def __keepalive_tick(self):
        """Timer callback: send watchdog ping and schedule next."""
        if not self.__av_started or not self.__listen:
            return
        self.__send_watchdog_ping()
        self.__keepalive_timer = threading.Timer(
            self.KEEPALIVE_INTERVAL, self.__keepalive_tick
        )
        self.__keepalive_timer.daemon = True
        self.__keepalive_timer.start()

    def __send_watchdog_ping(self):
        """Send a single watchdog keepalive ping to the Stalker portal."""
        try:
            addon = xbmcaddon.Addon()
            server_address = addon.getSetting('server_address')
            mac_address = addon.getSetting('mac_address')
            serial_number = addon.getSetting('serial_number')
            alt_ctx = addon.getSetting('alternative_context_path') == 'true'
            if not server_address or not mac_address:
                return

            # Construct portal URL (same logic as globals.py)
            split = urlsplit(server_address)
            base_url = split.scheme + '://' + split.netloc
            ctx_path = '/portal.php' if alt_ctx else '/server/load.php'
            if server_address.endswith('/c/'):
                portal_url = server_address.replace('/c/', '') + ctx_path
            elif server_address.endswith('/c'):
                portal_url = server_address.replace('/c', '') + ctx_path
            else:
                portal_url = base_url + '/stalker_portal' + ctx_path

            # Read token from cache file
            profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
            token_path = os.path.join(profile, 'token.json')
            token = ''
            try:
                with xbmcvfs.File(token_path, 'r') as f:
                    token_data = json.loads(f.read())
                    token = token_data.get('value', '')
            except (IOError, TypeError, ValueError, KeyError):
                return

            if not token:
                return

            headers = {
                'Cookie': 'mac=' + mac_address,
                'SN': serial_number,
                'Authorization': 'Bearer ' + token,
                'X-User-Agent': 'Model: MAG250; Link: WiFi',
                'Referrer': server_address,
                'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C) '
                              'AppleWebKit/533.3 (KHTML, like Gecko) '
                              'MAG200 stbapp ver: 2 rev: 250 Safari/533.3'
            }
            requests.get(
                url=portal_url, headers=headers,
                params={
                    'type': 'watchdog', 'action': 'get_events',
                    'init': '0', 'cur_play_type': '1', 'event_active_id': '0'
                },
                timeout=10
            )
            Logger.debug('Keepalive: watchdog ping sent')
        except Exception as exc:
            Logger.warn('Keepalive: watchdog ping failed: {}'.format(exc))


def run():
    """ Run the BackgroundService """
    BackgroundService().run()
