import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
from collections import Counter
import matplotlib.pyplot as plt

# Set up
st.set_page_config(
    page_title="Spotify Listening Analytics",
    page_icon="🎵",
    layout="wide",
)

st.markdown(
    """
    <style>

    .main {
        padding-top: 1rem;
    }

    .block-container {
        max-width: 1400px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    h1 {
        font-size: 3rem !important;
        margin-bottom: 0.2rem !important;
    }

    h2 {
        margin-top: 1rem !important;
    }

    .subtitle {
        color: #888888;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    .artist-card {
        padding: 10px;
        text-align: center;
    }

    .artist-rank {
        font-size: 1.5rem;
        font-weight: bold;
        margin-bottom: 5px;
    }

    .artist-name {
        font-size: 1rem;
        font-weight: 600;
        margin-top: 8px;
    }

    .metric-card {
        padding: 20px;
        border-radius: 12px;
        background-color: rgba(128, 128, 128, 0.08);
        text-align: center;
    }

    .section-description {
        color: #888888;
        margin-bottom: 15px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


st.title("🎵 Spotify Listening Analytics")

st.markdown(
    '<div class="subtitle">'
    "Explore your Spotify listening habits, favourite artists, and music genres."
    "</div>",
    unsafe_allow_html=True,
)

# SPOTIFY AUTHENTICATION

try:
    client_id = st.secrets["SPOTIFY_CLIENT_ID"]
    client_secret = st.secrets["SPOTIFY_CLIENT_SECRET"]
    redirect_uri = st.secrets["SPOTIFY_REDIRECT_URI"]

except Exception:
    st.error(
        "Spotify credentials could not be found. "
        "Check your .streamlit/secrets.toml file."
    )
    st.stop()

scope = "user-top-read"

try:
    sp_oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        open_browser=False,
    )

    token_info = sp_oauth.get_cached_token()

    if not token_info:
        auth_url = sp_oauth.get_authorize_url()

        st.warning("Please connect your Spotify account.")

        st.link_button(
            "🎧 Connect Spotify",
            auth_url,
        )

        st.stop()

    sp = spotipy.Spotify(
        auth_manager=sp_oauth
    )

except Exception as e:
    st.error(f"Spotify authentication failed: {e}")
    st.stop()


# SIDEBAR CONTROLS
st.sidebar.title(" Dashboard Controls")

time_range_label = st.sidebar.selectbox(
    "Listening period",
    [
        "Last 4 Weeks",
        "Last 6 Months",
        "All Time",
    ],
)

artist_limit = st.sidebar.slider(
    "Number of artists",
    min_value=5,
    max_value=50,
    value=20,
)


time_range_map = {
    "Last 4 Weeks": "short_term",
    "Last 6 Months": "medium_term",
    "All Time": "long_term",
}

time_range = time_range_map[time_range_label]



# MUSICBRAINZ genre lookup

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2"

HEADERS = {
    "User-Agent": "SpotifyListeningProfile/1.0 (local Streamlit app)"
}


@st.cache_data(ttl=86400)
def get_musicbrainz_genres(artist_name):

    try:

        search_url = f"{MUSICBRAINZ_URL}/artist/"

        params = {
            "query": f'artist:"{artist_name}"',
            "fmt": "json",
            "limit": 5,
        }

        response = requests.get(
            search_url,
            params=params,
            headers=HEADERS,
            timeout=10,
        )

        if response.status_code != 200:
            return []

        data = response.json()

        artists = data.get("artists", [])

        if not artists:
            return []

        # Find the best result
        best_artist = artists[0]

        for artist in artists:

            if artist.get("name", "").lower() == artist_name.lower():
                best_artist = artist
                break

        mbid = best_artist.get("id")

        if not mbid:
            return []

        lookup_url = f"{MUSICBRAINZ_URL}/artist/{mbid}"

        lookup_params = {
            "fmt": "json",
            "inc": "genres+tags",
        }

        lookup_response = requests.get(
            lookup_url,
            params=lookup_params,
            headers=HEADERS,
            timeout=10,
        )

        if lookup_response.status_code != 200:
            return []

        artist_data = lookup_response.json()

        genres = []

        for genre in artist_data.get("genres", []):
            name = genre.get("name")

            if name:
                genres.append(name.lower())

        for tag in artist_data.get("tags", []):
            name = tag.get("name")

            if name:
                genres.append(name.lower())

        # Remove duplicates
        genres = list(dict.fromkeys(genres))

        # Remove generic tags
        ignored = {
            "music",
            "seen live",
            "favorites",
            "favourite",
            "favorite",
            "albums",
            "songs",
            "usa",
            "american",
            "uk",
            "british",
        }

        genres = [
            genre
            for genre in genres
            if genre not in ignored
        ]

        return genres[:10]

    except Exception:
        return []


# GET SPOTIFY DATA
try:

    top_artists = sp.current_user_top_artists(
        limit=artist_limit,
        time_range=time_range,
    )

except Exception as e:

    st.error(f"Could not retrieve Spotify data: {e}")
    st.stop()


artists = top_artists.get("items", [])


if not artists:

    st.warning(
        "Spotify did not return any top artists for this period."
    )
    st.stop()

# match artists with genres
artist_data = []

with st.spinner("Loading your Spotify listening profile..."):

    for artist in artists:

        spotify_genres = artist.get("genres", [])

        if spotify_genres:

            genres = spotify_genres

        else:

            genres = get_musicbrainz_genres(
                artist["name"]
            )

        artist_data.append(
            {
                "name": artist["name"],
                "image": (
                    artist["images"][0]["url"]
                    if artist.get("images")
                    else None
                ),
                "genres": genres,
                "spotify_url": artist.get("external_urls", {}).get(
                    "spotify"
                ),
            }
        )

# SUMMARY METRICS

all_genres = []

for artist in artist_data:
    all_genres.extend(artist["genres"])


genre_counts = Counter(all_genres)


unique_genres = len(genre_counts)


col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "🎤 Artists",
        len(artist_data),
    )

with col2:
    st.metric(
        "🎶 Genres",
        unique_genres,
    )

with col3:

    if genre_counts:
        top_genre = genre_counts.most_common(1)[0][0]
    else:
        top_genre = "Not available"

    st.metric(
        "🔥 Top Genre",
        top_genre.title(),
    )


st.divider()

# TOP ARTISTS

with st.expander(
    "🎶 Genre Breakdown",
    expanded=True,
):

    st.markdown(
        '<div class="section-description">'
        "Genres associated with your top artists."
        "</div>",
        unsafe_allow_html=True,
    )

    if genre_counts:

        chart_col, list_col = st.columns(
            [2, 1]
        )

        with chart_col:

            # Use the 8 most common genres for the pie chart
            top_genres = genre_counts.most_common(8)

            genre_names = [
                genre.title()
                for genre, count in top_genres
            ]

            genre_values = [
                count
                for genre, count in top_genres
            ]

            fig, ax = plt.subplots(
                figsize=(7, 7)
            )

            ax.pie(
                genre_values,
                labels=genre_names,
                autopct="%1.1f%%",
                startangle=90,
            )

            ax.set_title(
                "Genre Breakdown"
            )

            ax.axis("equal")

            plt.tight_layout()

            st.pyplot(
                fig,
                use_container_width=True,
            )

            plt.close(fig)

        with list_col:

            st.subheader(
                "Top Genres"
            )

            for genre, count in genre_counts.most_common(10):

                st.write(
                    f"**{genre.title()}** — {count} artist"
                    + ("s" if count != 1 else "")
                )

    else:

        st.info(
            "No genre information was found for your artists."
        )


# GENRE BREAKDOWN
with st.expander(
    "🎶 Genre Breakdown",
    expanded=True,
):

    st.markdown(
        '<div class="section-description">'
        "Genres associated with your top artists."
        "</div>",
        unsafe_allow_html=True,
    )

    if genre_counts:

        chart_col, list_col = st.columns(
            [2, 1]
        )

        with chart_col:

            top_genres = genre_counts.most_common(12)

            genre_names = [
                genre.title()
                for genre, count in top_genres
            ]

            genre_values = [
                count
                for genre, count in top_genres
            ]

            fig, ax = plt.subplots(
                figsize=(9, 5)
            )

            ax.barh(
                genre_names[::-1],
                genre_values[::-1],
            )

            ax.set_xlabel(
                "Number of Artists"
            )

            ax.set_title(
                "Most Common Genres"
            )

            plt.tight_layout()

            st.pyplot(
                fig,
                use_container_width=True,
            )

            plt.close(fig)

        with list_col:

            st.subheader(
                "Top Genres"
            )

            for genre, count in genre_counts.most_common(10):

                st.write(
                    f"**{genre.title()}** — {count} artist"
                    + ("s" if count != 1 else "")
                )

    else:

        st.info(
            "No genre information was found for your artists."
        )


# account info

with st.expander(
    "👤 Spotify Account",
    expanded=False,
):

    try:

        current_user = sp.current_user()

        display_name = current_user.get(
            "display_name",
            "Spotify User",
        )

        followers = current_user.get(
            "followers",
            {},
        ).get(
            "total",
            0,
        )

        country = current_user.get(
            "country",
            "Unknown",
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "User",
                display_name,
            )

        with col2:
            st.metric(
                "Followers",
                followers,
            )

        with col3:
            st.metric(
                "Country",
                country,
            )

    except Exception:

        st.info(
            "Unable to load Spotify account information."
        )


with st.expander(
    "ℹ About This Dashboard",
    expanded=False,
):

    st.markdown(
        """
        ### Spotify Listening Analytics

        This dashboard analyses your personal Spotify listening
        profile using real Spotify data.

        **Data sources**

        - Spotify Web API
        - MusicBrainz for additional genre information

        **Features**

        - Top artist rankings
        - Listening-period comparison
        - Genre breakdown
        - Artist genre profiles
        - Spotify account information
        - Interactive expandable sections

        Genre information can sometimes be unavailable because
        Spotify does not always return genre metadata for artists.
        MusicBrainz is therefore used as a secondary source.

        No fake or randomly generated listening data is used.
        """
    )

# footer
st.divider()
st.caption(
    "Built with Python • Streamlit • Spotify Web API • MusicBrainz"
)