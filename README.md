Web application developed in Python with Flask that integrates with the Spotify API to automatically create playlists based on the genres of your Liked Songs. The application does the following tasks:
- Authenticates the user via OAuth with Spotify.
- Loads the user's "Liked Songs."
- Extracts the genres of each artist (using a cache to minimize API calls).
- Groups songs by genre and creates a playlist for each.
- Adds the corresponding songs to each playlist, processing them in batches to comply with API restrictions.

The application prints debugging messages to the console, indicating the status of each stage of the process, which playlist is being created, etc.
Since the Spotify API does not provide the genre of a song, the application determines the genre based on its artists. Additionally, not all artists have a defined genre, so their songs are placed in a "no genre" playlist.

## Requirements

- **Python 3**
- Register an application in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/) to obtain your Client ID and Client Secret.

## Install

1. **Clone the repository:**

   ```bash
   git clone https://github.com/fedetournier/spotify-liked-songs-into-genre-playlists.git
   cd spotify-liked-songs-into-genre-playlists
   ```

2. **Install the required dependencies:**

   ```bash
   pip install Flask requests
   ```

3. **Configure Spotify credentials:**

   Modify `app.py` by setting the following variables with your credentials:

   ```python
   app.secret_key = 'arbitrary string'
   CLIENT_ID = 'YOUR_SPOTIFY_CLIENT_ID'
   CLIENT_SECRET = 'YOUR_SPOTIFY_CLIENT_SECRET'
   REDIRECT_URI = 'http://localhost:5000/callback'
   ```

4. **Run the app:**

   ```bash
   python app.py
   ```

   The app will execute in `http://localhost:5000`.

## Usage

1. **Log in with Spotify:**

   Visit `http://localhost:5000` and click on "Log in with Spotify." You will be redirected to the Spotify authorization page.

2. **Authorize the application:**  

   Log in with your Spotify account and grant the requested permissions.  

3. **Song processing:**  

   The application will retrieve your saved songs, extract the genres of each artist (using the cache), and generate playlists based on those genres.  

4. **Verify the playlists:**  

   Once the process is complete, new playlists will be created in your Spotify account, each corresponding to a detected genre.

---
