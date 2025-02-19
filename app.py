import requests
import urllib.parse
import time
import json
import os
from datetime import datetime, timedelta
from flask import Flask, redirect, request, jsonify, session

app = Flask(__name__)

###########################################################
# Spotify API credentials and configuration
app.secret_key = ''
CLIENT_ID = ''
CLIENT_SECRET = ''
REDIRECT_URI = 'http://localhost:5000/callback'
###########################################################

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'

savedSongsIDs = []
savedArtistsIDs = []
genresToSongs = {} # Dictionary: genre -> [list of song URIs]

CACHE_FILE = "artists_cache.json"

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as file:
        artists_cache = json.load(file)
else:
    artists_cache = {}

def save_cache():
    with open(CACHE_FILE, "w") as file:
        json.dump(artists_cache, file)

# ------------------------ APPLICATION ROUTES ------------------------

@app.route('/')
def index():
    return "<a href='/login'>Log in with Spotify</a>"

@app.route('/login')
def login():
    scope = ('user-read-private user-read-email user-library-read '
             'playlist-modify-public playlist-modify-private')
    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': REDIRECT_URI,
        'show_dialog': True
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    if 'error' in request.args:
        return jsonify({"error": request.args['error']})

    req_body = {
        'code': request.args.get('code'),
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    response = requests.post(TOKEN_URL, data=req_body)
    token_info = response.json()

    session['access_token'] = token_info['access_token']
    session['refresh_token'] = token_info['refresh_token']
    session['expires_at'] = datetime.now().timestamp() + token_info['expires_in']
    return redirect('/saved')

@app.route('/saved')
def get_saved(): # Retrieves the user's saved songs, extracts song and artist IDs, and stores them in global lists.
    if 'access_token' not in session:
        return redirect('/login')
    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    headers = {'Authorization': f"Bearer {session['access_token']}"}
    
    # The Spotify API allows up to 50 songs per request.
    response = requests.get(API_BASE_URL + 'me/tracks?limit=50&offset=0', headers=headers)
    data = response.json()
    total = data['total']
    limit = ((total + 49) // 50) * 50

    for offset in range(50, limit + 1, 50):
        items = data['items']
        for song in items:
            track = song['track']
            track_id = track['id']
            savedSongsIDs.append(track_id)

            artistsData = track['artists']
            if len(artistsData) > 1:
                artistsIDs = ",".join([artist['id'] for artist in artistsData])
            else:
                artistsIDs = artistsData[0]['id']
            savedArtistsIDs.append(artistsIDs)

        response = requests.get(API_BASE_URL + f'me/tracks?limit=50&offset={offset}', headers=headers)
        data = response.json()

    return redirect('/genres')

@app.route('/genres')
def get_genres():
    if 'access_token' not in session:
        return redirect('/login')
    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')
    
    headers = {'Authorization': f"Bearer {session['access_token']}"}

    songsData = [] # List to store songs {songID, genres}
    artistIDs_to_fetch = set() # Set of unique IDs to optimize requests
    song_to_artists = []

    for i, songArtists in enumerate(savedArtistsIDs):
        individualArtists = songArtists.split(",")
        song_to_artists.append((savedSongsIDs[i], individualArtists))
        artistIDs_to_fetch.update(individualArtists)
    
    print(f"Total unique artists before filtering cache: {len(artistIDs_to_fetch)}")
    artistIDs_to_fetch = [aid for aid in artistIDs_to_fetch if aid not in artists_cache]
    print(f"We need to request data for {len(artistIDs_to_fetch)} artists to the API.")
    batch_size = 50

    for i in range(0, len(artistIDs_to_fetch), batch_size):
        batch = artistIDs_to_fetch[i:i + batch_size]
        artistIDs_str = ",".join(batch)
        print(f"Sending request with {len(batch)} artists...")
        response = requests.get(API_BASE_URL + f'artists?ids={artistIDs_str}', headers=headers)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            print(f"ERROR 429: Too many requests. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            continue
        
        if response.status_code != 200:
            print(f"ERROR {response.status_code}: {response.text}")
            continue
        
        try:
            artistsList = response.json()
        except requests.exceptions.JSONDecodeError:
            print("ERROR: API response is not valid JSON.")
            continue
        
        # Update the cache with the genres of each artist
        for artist in artistsList.get("artists", []):
            artistID = artist.get("id", "UNKNOWN_ID")
            artist_genres = artist.get("genres", [])
            artists_cache[artistID] = artist_genres
        
        save_cache()
        time.sleep(1)
    
    print("Genres collected for", len(artists_cache), "in the cache.")

    for songID, artistIDs in song_to_artists:
        combinedGenres = set()
        for artistID in artistIDs:
            genres = artists_cache.get(artistID, [])
            combinedGenres.update(genres)
        if not combinedGenres:
            combinedGenres.add("unknown genre")
        
        song_data = {
            "songID": songID,
            "genres": list(combinedGenres)
        }
        songsData.append(song_data)
        
        for genre in combinedGenres:
            if genre not in genresToSongs:
                genresToSongs[genre] = []
            genresToSongs[genre].append(f"spotify:track:{songID}")
    
    return redirect('/generate')

@app.route('/generate')
def generate_playlists():
    if 'access_token' not in session:
        return redirect('/login')
    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')
    
    headers = {'Authorization': f"Bearer {session['access_token']}"}
    
    response = requests.get(API_BASE_URL + 'me', headers=headers)
    try:
        user_data = response.json()
    except requests.exceptions.JSONDecodeError:
        print(f"Error: The response is not a valid JSON. Código: {response.status_code}")
        print(f"Response: {response.text}")
        return "Error retrieving user data from Spotify."
    
    user_id = user_data['id']
    
    for genre, songIDs in genresToSongs.items():
        print(f"Creating playlist for genre: {genre}")
        playlistDescription = {
            'name': genre,
            'public': False,  # Change to True for public playlists
            'description': "Playlist made with 'github.com/fedetournier/spotify-liked-songs-into-genre-playlists'"
        }
        response = requests.post(API_BASE_URL + f'users/{user_id}/playlists', headers=headers, json=playlistDescription)
        try:
            playlist_data = response.json()
            if "id" not in playlist_data:
                print(f"Error creating the playlist for {genre}: {playlist_data}")
                continue
        except requests.exceptions.JSONDecodeError:
            print(f"Error: The response is not a valid JSON when creating a playlist for {genre}.")
            continue
        
        playlist_id = playlist_data['id']
        
        # The Spotify API allows up to 100 songs per request.
        for i in range(0, len(songIDs), 100):
            batch = songIDs[i:i + 100]
            playlistData = {'uris': batch}
            response = requests.post(API_BASE_URL + f'playlists/{playlist_id}/tracks', headers=headers, json=playlistData)
            if response.status_code != 201:
                print(f"Error adding songs to {genre}: {response.json()}")
    
    return "Playlists generated successfully!"

@app.route('/refresh-token')
def refresh_token():
    if 'refresh_token' not in session:
        return redirect('/login')
    
    if datetime.now().timestamp() > session['expires_at']:
        req_body = {
            'grant_type': 'refresh_token',
            'refresh_token': session['refresh_token'],
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }
        response = requests.post(TOKEN_URL, data=req_body)
        new_token_info = response.json()
        session['access_token'] = new_token_info['access_token']
        session['expires_at'] = datetime.now().timestamp() + new_token_info['expires_in']
    
    return redirect('/saved')

# Run the application
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
