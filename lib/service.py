# -*- coding: utf-8 -*-
""" Background service code """

from __future__ import absolute_import, division, unicode_literals

import os
from urllib.parse import urlsplit, parse_qsl, urlencode
import xbmc
import xbmcaddon
import xbmcgui
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

        while not self.abortRequested():
            # Stop when abort requested
            if self.waitForAbort(10):
                break

        Logger.debug('Service stopped')

    def onSettingsChanged(self):  # pylint: disable=invalid-name
        """React to setting changes:
        - Manual refresh toggle: run refresh_all and reset the toggle.
        - First-time setup: offer to pre-fetch all data when credentials are entered.
        """
        addon = xbmcaddon.Addon()

        # --- Manual refresh button (boolean toggle workaround) ---
        if addon.getSetting('refresh_all_data') == 'true':
            addon.setSetting('refresh_all_data', 'false')
            xbmc.executebuiltin(
                'RunPlugin(plugin://plugin.video.stalkervod.tmdb/?action=refresh_all)')
            return

        # --- First-time setup wizard ---
        server = addon.getSetting('server_address')
        mac = addon.getSetting('mac_address')
        if not server or not mac:
            return

        profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        flag_file = os.path.join(profile, 'initial_setup_done')
        if xbmcvfs.exists(flag_file):
            return

        # Mark as done before asking so repeated setting changes don't re-trigger
        handle = xbmcvfs.File(flag_file, 'w')
        handle.close()

        if xbmcgui.Dialog().yesno(
                addon.getLocalizedString(32113),
                addon.getLocalizedString(32114)):
            xbmc.executebuiltin(
                'RunPlugin(plugin://plugin.video.stalkervod.tmdb/?action=refresh_all)')


class PlayerMonitor(Player):
    """ A custom Player object to check subtitles """

    def __init__(self):
        """ Initialises a custom Player object """
        self.__listen = False
        self.__av_started = False
        self.__path = None
        Player.__init__(self)

    def onPlayBackStarted(self):  # pylint: disable=invalid-name
        """ Will be called when Kodi player starts """
        self.__path = getInfoLabel('Player.FilenameAndPath')
        if not self.__path.startswith('plugin://plugin.video.stalkervod/'):
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
        params = dict(parse_qsl(urlsplit(self.__path).query))
        episode_no = get_int_value(params, 'series')
        total_episodes = get_int_value(params, 'total_episodes')
        if episode_no != 0 and episode_no < total_episodes:
            params.update({'series': episode_no + 1})
            next_episode_url = '{}?{}'.format('plugin://plugin.video.stalkervod/', urlencode(params))
            get_next_info_and_send_signal(params, next_episode_url)

    def onPlayBackError(self):  # pylint: disable=invalid-name
        """ Will be called when playback stops due to an error. """
        if not self.__listen:
            return
        self.__av_started = False
        self.__listen = False
        Logger.debug('Stalker Player: [onPlayBackError] called')

    def onPlayBackEnded(self):  # pylint: disable=invalid-name
        """ Will be called when [Kodi] stops playing a file """
        if not self.__listen:
            return
        Logger.debug('Stalker Player: [onPlayBackEnded] called')
        self.__listen = False
        self.__av_started = False

    def onPlayBackStopped(self):  # pylint: disable=invalid-name
        """ Will be called when [user] stops Kodi playing a file """
        if not self.__listen:
            return
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


def run():
    """ Run the BackgroundService """
    BackgroundService().run()
