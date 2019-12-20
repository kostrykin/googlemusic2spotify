# googlemusic2spotify

Kinda quick'n'dirty written scripts:

- `googlemusic_export.py` – exports your Google Music playlists to JSON
- `spotify_import.py` – imports JSON playlists to your Spotify library

For my own library (2471 songs in 34 playlists) the import into Spotify performed as follows:

- 2156 songs imported successfully
- 48 bad matches (prompts for manual review)
- Failed to find correspondances for 291 songs (manual work required)
