"""

	utilities.py
	di MARIO GABRIELE CAROFANO

	Questo file raccoglie funzioni di utilità generiche utilizzate nei file di progetto.

"""

#   ########################################################################    #
#   LIBRERIE

import importlib
from pathlib import Path
from typing import Callable, Any

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth, SpotifyOauthError

import re
import unicodedata
import subprocess

from constants import *

#   ########################################################################    #
#   FUNZIONI DI UTILITÀ

def load_spotify_config():
	"""Importa in sicurezza il modulo config.py e controlla le variabili richieste."""

	try:
		config = importlib.import_module("config")

		return (
			config.SPOTIFY_CLIENT_ID if hasattr(config, "SPOTIFY_CLIENT_ID") else None,
			config.SPOTIFY_CLIENT_SECRET if hasattr(config, "SPOTIFY_CLIENT_SECRET") else None,
			config.SPOTIFY_REDIRECT_URI if hasattr(config, "SPOTIFY_REDIRECT_URI") else None
		)
	
	except Exception as e:
		return None, None, None

	# end

def get_spotify_client(id: str, secret: str, uri: str) -> Spotify | None:
	"""Restituisce un client Spotify autenticato.

	Args:
		id (str): il Client ID dell'account Developer.
		secret (str): il Client SECRET dell'account Developer.
		uri (str): il Redirect URI dell'account Developer.

	Returns:
		Spotify: il client Spotify.
	"""

	auth = SpotifyOAuth(
		client_id = id,
		client_secret = secret,
		redirect_uri = uri,
		scope = SPOTIFY_SCOPE,
		cache_path = SPOTIFY_CACHE_PATH,
		show_dialog = True,
		open_browser = True
	)

	try:
		sp = Spotify(auth_manager = auth)
		user = sp.current_user()
		print(f"✅ Autenticato come: {user['id']} | {user['display_name']}")

	except SpotifyOauthError as exc:
		if exc.error != "invalid_grant":
			print(f"⚠️ Errore di autenticazione: {exc}")
			return None

		# Da luglio 2026 Spotify applica anche ai progetti esistenti
		# una durata massima di sei mesi per i refresh token.
		# Si può risolvere questo problema rimuovendo la cache
		# e riprovando l'autenticazione.
		Path(SPOTIFY_CACHE_PATH).unlink(missing_ok=True)
		sp = Spotify(auth_manager = auth)

		user = sp.current_user()
		print(f"✅ Autenticato come: {user['id']} | {user['display_name']}")
	
	return sp
	
	# end
	
def get_safename(
	input_name: str,
	max_length: int = 35
) -> str:
	"""Crea un nome file sicuro per macOS, Windows e Linux. \n
	-	Rimuove caratteri speciali non ammessi (: / ? * < > | "). \n
	-	Normalizza gli accenti. \n
	-	Rimuove spazi doppi e caratteri di controllo. \n
	-	Tronca il nome se troppo lungo.

	Args:
		input_name (str): stringa di testo da elaborare.
		max_length (int, optional): lunghezza massima della string. Defaults to 35.

	Returns:
		str: il nome file sicuro.
	"""

	safe_name = input_name

	# Normalizza unicode (es. è -> e).
	safe_name = unicodedata.normalize("NFKD", safe_name)
	safe_name = safe_name.encode("ascii", "ignore").decode("ascii")

	# Rimuove caratteri non validi per filesystem.
	safe_name = re.sub(r'[\/:*?"<>|\\]', "_", safe_name)

	# Rimuove caratteri di controllo e punti finali.
	safe_name = re.sub(r'[\x00-\x1F]', '', safe_name).strip('. ')

	# Rimpiazza spazi multipli con uno solo.
	safe_name = re.sub(r'\s+', ' ', safe_name).strip()

	# Tronca se troppo lungo.
	if len(safe_name) > max_length:
		safe_name = safe_name[:max_length].rstrip()

	return safe_name

	# end

def normalize_result(item: dict, id_key: str) -> dict | None:
	"""Normalizza un elemento restituito da YTMusic in un dizionario standardizzato.

	Args:
		item (dict): Elemento "ytmusic" da normalizzare.
		id_key (str): chiave dell'ID del video all'interno dell'elemento.

	Returns:
		dict | None: dizionario standardizzato.
	"""
	
	video_id = item.get(id_key)
	title = item.get("title")
	duration_str = str(item.get("duration"))
	channel = (
		item.get("channel")
		or item.get("uploader")
		or item.get("channel_name")
	)

	if not video_id or not duration_str:
		return None

	# Converte la durata come stringa (es. "3:45") in secondi.
	try:
		if ":" not in duration_str:
			duration = int(duration_str)
		else:
			parts = list(map(int, duration_str.split(":")))
			duration = sum(p * 60**i for i, p in enumerate(reversed(parts)))
	except ValueError:
		return None

	norm_result = {
		"id": video_id,
		"duration": duration,
		"title": title or "",
		"channel": channel or ""
	}

	return norm_result

	# end

def convert_video(
    input_file: str | Path,
    output_file: str | Path,
) -> Path:
	"""Converte un video in MP4 H.264/AAC.

	Args:
		input_file (str | Path): il percorso del video sorgente.
		output_file (str | Path): il percorso del video convertito.

	Returns:
		Path: il percorso del video convertito.
	"""

	input_file = Path(input_file)
	output_file = Path(output_file)

	if not Path(FFMPEG_PATH).exists():
		raise FileNotFoundError(
			f"FFmpeg non trovato: {FFMPEG_PATH}"
		)

	if not input_file.exists():
		raise FileNotFoundError(
			f"Video sorgente non trovato: {input_file}"
		)

	output_file.parent.mkdir(parents=True, exist_ok=True)

	command = [
		FFMPEG_PATH,
		"-y",
		"-hide_banner",
		"-loglevel", "error",
		"-nostats",
		"-i", str(input_file),
		"-map", "0:v:0",
		"-map", "0:a:0?",
		"-vf", "scale=1280:-2",
		"-c:v", "h264_videotoolbox",
		"-profile:v", "high",
		"-q:v", "35",
		"-pix_fmt", "yuv420p",
		"-tag:v", "avc1",
		"-c:a", "aac",
		"-b:a", "160k",
		"-ar", "48000",
		"-ac", "2",
		"-movflags", "+faststart",
		str(output_file),
	]

	print(f"🎬 Conversione in corso: {output_file.name}")
	subprocess.run(command, check=True)

	return output_file

	# end
