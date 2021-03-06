
import spotipy
from spotipy.oauth2 import is_token_expired
from spotiman.objects import Device, Track, Playlist, User

import logging
import os, time

# Same as spotipy function but instead return sp_aouth object instead
def prompt_for_user_token(username, scope=None, client_id = None,
        client_secret = None, redirect_uri = None, cache_path = None):
    ''' prompts the user to login if necessary and returns
        the user token suitable for use with the spotipy.Spotify 
        constructor
        Parameters:
         - username - the Spotify username
         - scope - the desired scope of the request
         - client_id - the client id of your app
         - client_secret - the client secret of your app
         - redirect_uri - the redirect URI of your app
         - cache_path - path to location to save tokens
    '''

    if not client_id:
        client_id = os.getenv('SPOTIPY_CLIENT_ID')

    if not client_secret:
        client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')

    if not redirect_uri:
        redirect_uri = os.getenv('SPOTIPY_REDIRECT_URI')

    if not client_id:
        print('''
            You need to set your Spotify API credentials. You can do this by
            setting environment variables like so:
            export SPOTIPY_CLIENT_ID='your-spotify-client-id'
            export SPOTIPY_CLIENT_SECRET='your-spotify-client-secret'
            export SPOTIPY_REDIRECT_URI='your-app-redirect-url'
            Get your credentials at     
                https://developer.spotify.com/my-applications
        ''')
        raise spotipy.SpotifyException(550, -1, 'no credentials set')

    cache_path = cache_path or ".cache-" + username
    sp_oauth = spotipy.oauth2.SpotifyOAuth(client_id, client_secret, redirect_uri, 
        scope=scope, cache_path=cache_path)

    # try to get a valid token for this user, from the cache,
    # if not in the cache, the create a new (this will send
    # the user to a web page where they can authorize this app)

    token_info = sp_oauth.get_cached_token()

    if not token_info:
        print('''
            User authentication requires interaction with your
            web browser. Once you enter your credentials and
            give authorization, you will be redirected to
            a url.  Paste that url you were directed to to
            complete the authorization.
        ''')
        auth_url = sp_oauth.get_authorize_url()
        try:
            import webbrowser
            webbrowser.open(auth_url)
            print("Opened %s in your browser" % auth_url)
        except:
            print("Please navigate here: %s" % auth_url)

        print()
        print()
        try:
            response = raw_input("Enter the URL you were redirected to: ")
        except NameError:
            response = input("Enter the URL you were redirected to: ")

        print()
        print() 

        code = sp_oauth.parse_response_code(response)
        token_info = sp_oauth.get_access_token(code)
    # Auth'ed API request
    if token_info:
        return sp_oauth
    else:
        return None

class Spotify(spotipy.Spotify):

    # Same as the original but accepts the oauth2 object instead of token
    def __init__(self, auth=None, requests_session=True,
        client_credentials_manager=None, proxies=None, requests_timeout=None, oauth2=None):

        if oauth2 is not None:
            self.oauth2 = oauth2
            token = self.oauth2.get_cached_token()['access_token']
        else:
            token = None

        super().__init__(auth=token, requests_session=requests_session,
            client_credentials_manager=client_credentials_manager, 
            proxies=proxies, requests_timeout=requests_timeout)

    def _internal_call(self, method, url, payload, params):

        while True:

            try:
                self.refreshTokenIfExpired() # need to check every time instead of once

                return super()._internal_call(method, url, payload, params)
            except spotipy.SpotifyException as e:
                logging.warning('Spotify Exception!!!')
                logging.warning(str(e))
                time.sleep(1)
            except Exception as e:
                logging.warning('Requests exception!!!')
                logging.warning(str(e))
                time.sleep(1)

    def refreshTokenIfExpired(self):

        now = int(time.time())
        token_info = self.oauth2.get_cached_token()
        is_expired = ((token_info['expires_at'] - now) < 180)
        if is_expired:
            logging.debug("Token is expired. Fetching new token...")
            token_info = self.oauth2.refresh_access_token(token_info['refresh_token'])
            self._auth = token_info['access_token']
            logging.debug("Fetched new token...")
        else:
            logging.debug("%d seconds for the token to expire." % \
                    ((token_info['expires_at']-now)))


    def devices(self):
    
        return [Device(device) for device in super().devices()['devices']]

    def current_playback(self, market=None):

        raw = super().current_playback()

        if raw is not None:
            if 'item' in raw: 
                track = Track(raw['item'])
                del raw['item']
                return track, raw
        else:
            return None, None


    def user_playlist_tracks(self, user, playlist_id=None, fields=None,
                                limit=100, offset=0, market=None):

        raw = super().user_playlist_tracks(user.id, playlist_id=playlist_id, fields=fields,
                limit=limit, offset=offset, market=market)
        tracks = [Track(raw_track['track']) for raw_track in raw['items']]
        return tracks


    def current_user_playlists(self, limit=50, offset=0):

        raw = super().current_user_playlists(limit=limit, offset=offset)
        if len(raw['items']) > 0:
            playlists = [Playlist(item, self) for item in raw['items']]
            return playlists
        else:
            return []

    def me(self):

        return User(super().me())

