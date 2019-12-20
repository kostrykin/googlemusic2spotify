from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import ui

import time
import json
import googlemusic


OUTPUT_FILEPATH            = 'googlemusic_export.json'
OUTPUT_ILIKE_PLAYLIST_NAME = 'ILIKE'


with webdriver.Firefox() as driver:
    driver.get('https://play.google.com/music/listen?authuser')
    
    # Perform login
    print('Waiting for login')
    success = False
    try:
        ui.WebDriverWait(driver, googlemusic.LOGIN_WAIT_TIMEOUT).until(lambda driver: googlemusic.get_playlists_container(driver))
        print('Login successful')
        success = True
    except TimeoutException:
        import getpass
        getpass.getpass("Timeout. Press Enter after you are done logging in.")
        success = True
    except KeyboardInterrupt:
        print('')
    
    if success:
        playlist_names = googlemusic.get_playlist_names(driver)
        print(f'Found {len(playlist_names)} playlists')
        playlists = {}
        for playlist_name in playlist_names:
            print(f'  Reading playlist: {playlist_name}')
            googlemusic.open_playlist(driver, playlist_name)
            playlist = googlemusic.read_current_playlist(driver)
            playlists[playlist_name] = playlist
        print(f'  Reading "I like" playlist')
        assert OUTPUT_ILIKE_PLAYLIST_NAME not in playlists
        googlemusic.open_ilike_playlist(driver)
        playlist = googlemusic.read_current_playlist(driver)
        playlists[OUTPUT_ILIKE_PLAYLIST_NAME] = playlist
        print(f'Writing library to: {OUTPUT_FILEPATH}')
        with open(OUTPUT_FILEPATH, 'w') as outfile:
            json.dump(playlists, outfile)
