#!/usr/bin/env python3

import json
import sys
import numpy as np
import argparse
import time
import requests
import re
import click

sys.path.append('spotipy_repo')
import spotipy, spotipy.auth, spotipy.util, spotipy.scope

from datetime import datetime, timedelta


parser = argparse.ArgumentParser()
parser.add_argument('input', type=str, default=None)
parser.add_argument('--replace-existing-playlists', action='store_true', default=False)
parser.add_argument('--failures-output', default='spotify_import_failures.json')
parser.add_argument('--description', default='Imported from JSON')
parser.add_argument('--max-retry-count', type=int, default=10)
parser.add_argument('--ignore-tag', type=str, action='append', default=['unbekannt', 'unknown', 'none'])
args = parser.parse_args()


if args.input is None:
    playlists = json.load(sys.stdin)
else:
    with open(args.input, 'r') as fin:
        playlists = json.load(fin)


ignored_tag_values = [tag_value.lower() for tag_value in args.ignore_tag]


client_id     = '117b2e6dde2747bb848f55e16921ba08'
client_secret = '1a80b158f2464bfaad21d072f009fa8a'
user_token = spotipy.util.prompt_for_user_token(
    client_id,
    client_secret,
    'http://localhost',
    scope=spotipy.scope.every
)
sp = spotipy.Spotify(user_token)


current_user_id   = sp.current_user().id
current_playlists = [playlist for playlist in sp.all_items(sp.playlists(current_user_id))]
current_playlist_names_lower = [playlist.name.lower() for playlist in current_playlists]

def get_song_search_query(song, ignored_tags=['duration'], exact=True):
    assert len(song['title']) > 0
    tag_translator = {
            'title' : 'track',
            'artist': 'artist',
            'album' : 'album',
        }
    search_terms = []
    for song_tag in song.keys():
        if song_tag in ignored_tags: continue
        song_tag_value = song[song_tag]
        if len(song_tag_value) == 0 or song_tag_value.lower() in ignored_tag_values: continue
        if exact:
            song_tag_value = song_tag_value.replace('\\', '\\\\')
            song_tag_value = song_tag_value.replace( '"',  '\\"')
            term = f'{tag_translator[song_tag]}:"{song_tag_value}"' if song_tag in tag_translator else f'"{song_tag_value}"'
        else:
            term = re.sub(r'[^0-9a-zA-Z\'\u2019]+', ' ', song_tag_value)
        search_terms.append(term)
    return ' '.join(search_terms)

def rate_song_candidates(song, song_candidates):
    time     = datetime.strptime(song['duration'], '%M:%S')
    duration = timedelta(hours=time.hour, minutes=time.minute, seconds=time.second).total_seconds()
    ratings  = []
    for song_candidate_idx, song_candidate in enumerate(song_candidates):
        candidate_duration = round(song_candidate.duration_ms / 1000)
        duration_mismatch  = abs(candidate_duration - duration)
        candidate_rating   = 0 - 0.2 * song_candidate_idx - duration_mismatch
        ratings.append(candidate_rating)
    return ratings

def api_call(call, *call_args, verbose=False, **call_kwargs):
    retry_count = 1
    retry = True
    while retry:
        retry = False
        try: return call(*call_args, **call_kwargs)
        except requests.exceptions.HTTPError as ex:
            # 429: API rate limit exceeded
            # 502: Bad gateway
            if ex.response.status_code in [429, 502]:
                if retry_count < args.max_retry_count:
                    if verbose:
                        sys.stdout.write(f' ...retry' if retry_count == 1 else f' {retry_count}')
                        sys.stdout.flush()
                    time.sleep(retry_count)
                    retry = True
                    retry_count += 1
                    continue
            raise

for playlist_name in playlists.keys():
    if playlist_name.lower() in current_playlist_names_lower:
        if args.replace_existing_playlists:
            current_playlist_id = [playlist.id for playlist in current_playlists if playlist.name.lower() == playlist_name.lower()][0]
            api_call(sp.playlist_unfollow, current_playlist_id)
        else:
            raise Exception(f'Playlist "{playlist_name}" already exists')

print(f'Importing {len(playlists)} playlists')
failures = {}
total_imports = 0
for playlist_name, songs in playlists.items():
    print(f' Importing playlist: {playlist_name}')
    playlist  = api_call(sp.playlist_create, current_user_id, playlist_name, public=False, description=args.description)
    track_ids = []
    def submit_songs():
        if len(track_ids) > 0:
            sys.stdout.write(f' --- submitting')
            api_call(sp.playlist_tracks_add, playlist.id, track_ids, verbose=True)
            sys.stdout.write(f' ---\n')
            track_ids.clear()
    for song in songs:
        sys.stdout.write(f'  ...{song["title"]}')
        sys.stdout.flush()
        retry = True
        relax = 0
        # Relaxation level 1: Omit the album
        # Relaxation level 2: Do a non-exact look-up
        # Relaxation level 3: Omit the album and do a non-exact look-up
        while retry:
            retry = False
            song_search_query = get_song_search_query(song, ['duration'] + (['album'] if relax in [1, 3] else []), exact=(relax < 2))
            song_candidates = api_call(lambda: [song_candidate for song_candidate in sp.all_items(sp.search(song_search_query)[0])], verbose=True)
            try:
                if len(song_candidates) == 0:
                    if relax < 3:
                        sys.stdout.write(' ...relaxing')
                        sys.stdout.flush()
                        relax += 1
                        retry  = True
                        continue
                    else:
                        raise Exception('No candidates found')
                song_candidate_ratings = rate_song_candidates(song, song_candidates)
                song_resolution_idx    = np.argmax(song_candidate_ratings)
                song_resolution_rating = song_candidate_ratings[song_resolution_idx]
                song_resolution_id     = song_candidates[song_resolution_idx].id
                if song_resolution_rating < -10:
                    raise Exception('Bad match', song_resolution_rating, playlist.id, song_resolution_id)
                if song_resolution_id not in track_ids:
                    track_ids.append(song_resolution_id)
                sys.stdout.write(f' [OK]\n')
                total_imports += 1
                if len(track_ids) >= 10:
                    submit_songs()
            except Exception as ex:
                if len(ex.args) == 0: message = ''
                if len(ex.args) >= 1:
                    if ex.args[0] == 'Bad match':
                        message = f'{ex.args[0]}, {ex.args[1]}'
                        playlist_id        = ex.args[2]
                        song_resolution_id = ex.args[3]
                    else: message = ' '.join(ex.args)
                if playlist_name not in failures.keys(): failures[playlist_name] = []
                failure = {'song': song, 'reason': message}
                if message.startswith('Bad match'):
                    for extra in ['playlist_id', 'song_resolution_id']:
                        failure[extra] = locals()[extra]
                failures[playlist_name].append(failure)
                sys.stdout.write(f' [{message}]\n')
    submit_songs()
print(f'Imported {total_imports} songs')

bad_matches = []
for playlist_name, failed_imports in failures.items():
    for failure in failed_imports:
        if failure['reason'].startswith('Bad match'):
            bad_matches.append((playlist_name, failure))

if len(bad_matches) > 0:
    if click.confirm(f'\n{len(bad_matches)} bad matches. Do you want to review them now?', default=True):
        interrupt = False
        for playlist_name, failure in bad_matches:
            retry = True
            while retry:
                retry = False
                try:
                    api_call(sp.playback_start_tracks, [failure['song_resolution_id']])
                    api_call(sp.playback_resume)
                except requests.exceptions.HTTPError as ex:
                    if 'No active device found' in ' '.join(ex.args):
                        if click.confirm(' No active device found. Do you want to retry?', default=True):
                            retry = True
                        else:
                            interrupt = True
                    else: raise
            if interrupt: break
            song_search_query = get_song_search_query(failure['song'])
            if click.confirm(f' Accept this for {playlist_name}? {song_search_query}', default=True):
                api_call(sp.playlist_tracks_add, failure['playlist_id'], [failure['song_resolution_id']])
                failures[playlist_name].remove(failure)

with open(args.failures_output, 'w') as fout:
    json.dump(failures, fout)

total_failures = len(sum(failures.values(), []))

if len(failures) > 0:
    print(f'\nFailed to import {total_failures} songs:')
    for playlist_name, failed_imports in failures.items():
        print(f' Playlist: {playlist_name}')
        for failed_import in failed_imports:
            song_search_query = get_song_search_query(failed_import['song'])
            print(f'  {song_search_query} [{failed_import["reason"]}]')
