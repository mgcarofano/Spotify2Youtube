"""

	constants.py
	di MARIO GABRIELE CAROFANO

	Questo file raccoglie tutti i valori costanti utilizzati nei file di progetto.

"""

from enum import Enum

#	########################################################################	#
#	COSTANTI

SPOTIFY_SCOPE = "user-read-private playlist-modify-private playlist-modify-public"
""" Ambiti di autorizzazione richiesti all'utente durante l'autenticazione Spotify. """

SPOTIFY_CACHE_PATH = ".spotify_cache"
""" Path del file dove il pacchetto Spotipy salva il token. """

SPOTIFY_REQUEST_LIMIT = 100
""" Numero massimo di brani da richiedere per chiamata alle API di Spotify. """

SPOTIFY_ARTISTS_LIMIT = 4
""" Numero massimo di artisti da includere nella stringa della traccia. """

SPOTIFY_QUERY_LIMIT = 5
""" Limite massimo di risultati di una ricerca su Spotify. """

YOUTUBE_DURATION_LIMIT = 600
""" Limite massimo di secondi della durata di un video Youtube. """

YOUTUBE_QUERY_LIMIT = "10"
""" Limite massimo di risultati di una ricerca su Youtube. """

YOUTUBE_SEARCH_OPTIONS = {
	"skip_download": True,
	"quiet": True,
	"no_warnings": True
}
""" Opzioni di configurazione di yt-dlp per la ricerca di video senza download. """

YOUTUBE_DOWNLOAD_AUDIO_OPTIONS = {
	"format": "bestaudio/best",
	"postprocessors": [{
		"key": "FFmpegExtractAudio",
		"preferredcodec": "mp3",
		"preferredquality": "192",
	}],
	"quiet": True,
	"no_warnings": True
}
""" Opzioni di yt-dlp per scaricare e convertire i video in file audio MP3. """

YOUTUBE_DOWNLOAD_VIDEO_OPTIONS = {
	"format": "bestvideo[height<=240]+bestaudio/best[height<=240]",
	"merge_output_format": "mp4",
	"quiet": True,
	"no_warnings": True
}
""" Opzioni di yt-dlp per scaricare i video alla risoluzione più bassa disponibile. """

#	########################################################################	#
#	ENUMERAZIONI

class QueryType(Enum):
	""" Definisce le tipologie di ricerca su YouTube utilizzabili per ciascuna traccia. """

	VIDEO		= "official video"
	AUDIO		= "official audio"
	LYRIC		= "lyrics"
	EXTENDED	= "extended mix"

	# end class

QUERY_LIST = list(QueryType)

class MenuItems(Enum):
	""" Definisce le voci disponibili nel menu interattivo. """
	
	CREATE_PLAYLIST 	= "Crea playlist"
	ADD_PLAYLIST		= "Aggiungi playlist da Spotify"
	PRINT_PLAYLIST		= "Visualizza playlist inserite"
	PROCESS_PLAYLIST	= "Cerca playlist su Youtube"
	DOWNLOAD_PLAYLIST	= "Scarica playlist da Youtube"
	EXIT				= "Esci"

	# end class

MENU_LIST = list(MenuItems)