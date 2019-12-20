from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import ui, expected_conditions

import time
import aux


DEFAULT_WAIT_TIMEOUT = aux.DEFAULT_WAIT_TIMEOUT
LOGIN_WAIT_TIMEOUT   = aux.LOGIN_WAIT_TIMEOUT

ID_PLAYLIST_DRAWER_BTN = 'playlist-drawer-button'
ID_PLAYLIST_CONTAINER  = 'playlists-container'
ID_MAIN_CONTAINER      = 'mainContainer'
ID_MUSIC_CONTENT       = 'music-content'

CLASS_PLAYLIST_TITLE = 'playlist-title'
CLASS_SONG_TABLE     = 'song-table'
CLASS_SONG_ROW       = 'song-row'


def get_playlists_container(driver):
    elem = driver.find_element_by_id('playlists-container')
    return elem


def get_playlist_names(driver, recur=0):
    playlist_container = get_playlists_container(driver)
    playlist_names = [playlist.text for playlist in playlist_container.find_elements_by_class_name(CLASS_PLAYLIST_TITLE)]
    if len(playlist_names) == 0 or any(len(name) == 0 for name in playlist_names):
        ui.WebDriverWait(driver, DEFAULT_WAIT_TIMEOUT).until(expected_conditions.element_to_be_clickable((By.ID, ID_PLAYLIST_DRAWER_BTN)))
        elem = driver.find_element_by_id(ID_PLAYLIST_DRAWER_BTN)
        elem.click()
        time.sleep(recur)
        playlist_names = get_playlist_names(driver, recur + 1)
    return playlist_names


def open_playlists_menu(driver): get_playlist_names(driver)


def _open_playlist(driver, playlist_btn):
    playlist_name = playlist_btn.text
    playlist_btn.click()
    ui.WebDriverWait(driver, DEFAULT_WAIT_TIMEOUT).until(lambda driver: driver.find_elements_by_class_name(CLASS_SONG_TABLE))
    waittime = 0
    while True:
        current_playlist_name = driver.find_element_by_xpath(f'//*[@id="{ID_MUSIC_CONTENT}"]//*/h2').text
        if current_playlist_name != playlist_name:
            time.sleep(1)
            waittime += 1
            if waittime > DEFAULT_WAIT_TIMEOUT: raise Exception('Timeout: Failed to open playlist')
        else: break


def open_playlist(driver, playlist_name):
    playlist_names = get_playlist_names(driver)
    playlist_idx = playlist_names.index(playlist_name)
    xpath = f'//*[@id="{ID_PLAYLIST_CONTAINER}"]/div[{playlist_idx + 1}]/a/div'
    playlist_btn = driver.find_element_by_xpath(xpath)
    driver.execute_script('arguments[0].scrollIntoView();', playlist_btn)
    ui.WebDriverWait(driver, DEFAULT_WAIT_TIMEOUT).until(expected_conditions.element_to_be_clickable((By.XPATH, xpath)))
    _open_playlist(driver, playlist_btn)


def open_ilike_playlist(driver):
    open_playlists_menu(driver)
    xpath = f'//*[@id="{ID_MAIN_CONTAINER}"]/div[1]/div[1]/a/div'
    playlist_btn = driver.find_element_by_xpath(xpath)
    driver.execute_script('arguments[0].scrollIntoView();', playlist_btn)
    ui.WebDriverWait(driver, DEFAULT_WAIT_TIMEOUT).until(expected_conditions.element_to_be_clickable((By.XPATH, xpath)))
    _open_playlist(driver, playlist_btn)


def read_current_playlist(driver):
    driver.execute_script('window.scrollTo(0,0);')
    songs = []
    thead = driver.find_element_by_xpath(f'//*[@id="{ID_MUSIC_CONTENT}"]//*/thead')
    field_offset = 0 if len(thead.find_elements_by_xpath('tr[1]/th[@data-col="index"]')) == 0 else 1
    while True:
        tbody = driver.find_element_by_xpath(f'//*[@id="{ID_MUSIC_CONTENT}"]//*/tbody')
        total_song_count = int(tbody.get_attribute('data-count'))
        playlist_rows = tbody.find_elements_by_xpath(f'//*[contains(@class, "{CLASS_SONG_TABLE}")]/*/tr[contains(@class, "{CLASS_SONG_ROW}")]')
        for playlist_row in playlist_rows:
            row_index = int(playlist_row.get_attribute('data-index'))
            expected_row_index = len(songs)
            if row_index < expected_row_index: continue
            if row_index > expected_row_index: raise Exception('Failed to fetch song data')
            try:
                song = {
                        'title'   : playlist_row.find_element_by_xpath(f'td[{1 + field_offset}]/span'  ).text,
                        'duration': playlist_row.find_element_by_xpath(f'td[{2 + field_offset}]/span'  ).text,
                        'artist'  : playlist_row.find_element_by_xpath(f'td[{3 + field_offset}]/span/a').text,
                        'album'   : playlist_row.find_element_by_xpath(f'td[{4 + field_offset}]/span/a').text
                    }
            except:
                print(f'Error reading song with index {row_index}')
                raise
            songs.append(song)
        if len(songs) < total_song_count:
            driver.execute_script('arguments[0].scrollIntoView();', playlist_rows[-1])
        else:
            break
    return songs

