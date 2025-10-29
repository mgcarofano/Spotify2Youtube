"""

	spotify2youtube.py
	di MARIO GABRIELE CAROFANO
	
	Script interattivo per importare playlist da Spotify, cercare
	i relativi brani su YouTube e scaricarne automaticamente i
	file multimediali (audio o video).

	Offre le seguenti funzionalità:
	1.	Estrazione Playlist da Spotify:
		-	Autenticazione tramite le API Spotify (spotipy).
		-	Recupera titolo e artisti di tutti i brani di una playlist.
		-	Esporta i dati in un file CSV locale.
		-	Il percorso dell'output può essere modificato.
	2.	Ricerca su YouTube:
		-	Utilizza yt-dlp per cercare il miglior video corrispondente
		ad ogni brano.
		-	Supporta molteplici modalità di ricerca definite da 'QueryType'.
	3.	Download automatico:
		-	Legge i file CSV generati e utilizza 'yt-dlp' per scaricare
		i file multimediali (audio o video).
		-	Il percorso dei download può essere modificato.
	
	Dal menù interattivo, si può collegare l’account Spotify Developer
	digitando il client ID, il client SECRET e il redirect URI (oppure si
	possono salvare in un file config.py dedicato).

"""

#	########################################################################	#
#	LIBRERIE

from datetime import datetime
import random
import time

import csv
import os
from tqdm import tqdm

import re
import unicodedata

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from yt_dlp import YoutubeDL

import curses
from curses import wrapper

import importlib
from constants import *

#	########################################################################	#
#	CONTROLLO di VALIDITÀ del file config.py

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

#	########################################################################	#
#	CONTROLLO di VALIDITÀ dei nomi

def get_safename(
	input_name: str,
	max_length: int = 35
) -> str:
	"""Crea un nome file sicuro per macOS, Windows e Linux. \n
	-	Rimuove caratteri speciali non ammessi (: / ? * < > | \ "). \n
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

#	########################################################################	#
#	AUTENTICAZIONE in SPOTIFY

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

	sp = Spotify(auth_manager = auth)

	try:
		user = sp.current_user()
		print(f"✅ Autenticato come: {user['id']} | {user['display_name']}")
	except Exception as e:
		print(f"⚠️ Utente non autenticato: {e}")
		return None
	
	return sp
	
	# end

#	########################################################################	#
#	CREAZIONE della playlist

def search_spotify_tracks(sp: Spotify, query: str) -> list | None:
	"""Esegue una ricerca su Spotify e restituisce i risultati, se esistono.

	Args:
		sp (Spotify): il client Spotify.
		query (str): il brano da cercare su Spotify.

	Returns:
		list: i risultati della ricerca.
	"""

	found_tracks = []

	results = sp.search(
		q=query,
		limit=SPOTIFY_QUERY_LIMIT,
		type='track'
	)

	tracks = results.get("tracks", {}).get("items", [])
	if not tracks:
		print("❌ Nessun risultato trovato.")
		return

	print("\nRisultati trovati:")
	for i, t in enumerate(tracks, 1):
		found_tracks.append({
			"id": t["id"],
			"name": t["name"],
			"artists": ", ".join(
				artist["name"]
				for artist
				in t["artists"][:SPOTIFY_ARTISTS_LIMIT]
			)
		})
		print(f"{i}. {found_tracks[i-1]['name']} — {found_tracks[i-1]['artists']}")
	
	return found_tracks

	# end

def upload_spotify_playlist(sp: Spotify, playlist_name: str, selected_tracks: list) -> str | None:
	"""Crea una nuova playlist Spotify partendo da brani cercati da terminale.

	Args:
		sp (Spotify): il client Spotify.
		playlist_name: nome scelto per la playlist da creare.
		selected_tracks (list): una lista contenente gli ID Spotify dei brani da aggiungere.

	Returns:
		str: ID spotify della playlist.
	"""

	try:

		user_id = sp.current_user()["id"]
		new_playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=False)
		playlist_id = new_playlist["id"]

		sp.playlist_add_items(playlist_id, selected_tracks)

		return playlist_id

	except Exception as e:
		print(f"❌ Errore durante la creazione della playlist: {e}")
		return None

	# end

#	########################################################################	#
#	ELABORAZIONE e SALVATAGGIO delle playlists

def get_playlist_id_from_url(playlist_url: str) -> str | None:
	"""Estrae l'ID Spotify di una playlist dal suo URL.

	Args:
		playlist_url (str): URL della playlist Spotify.

	Returns:
		str: ID spotify della playlist.
	"""

	match = re.search(r"playlist/([A-Za-z0-9]+)", playlist_url)
	if not match:
		print("❌ Impossibile estrarre l'id della playlist.")
		return None
	
	return match.group(1)

	# end

def extract_playlist_tracks(sp: Spotify, playlist_id: str) -> list[dict]:
	"""Estrae titolo e artisti da una playlist Spotify.

	Args:
		sp (Spotify): il client Spotify.
		playlist_id (str): ID Spotify di una playlist.
	
	Returns:
		list[dict]: gli elementi della playlist, composti da "track_name" e "track_artists".
	"""

	results = []

	playlist = sp.playlist(playlist_id)
	total_tracks = playlist["tracks"]["total"]

	for offset in range(0, total_tracks, SPOTIFY_REQUEST_LIMIT):
		
		# Si estraggono i dati di 'limit' brani dalla playlist.
		data = sp.playlist_tracks(
			playlist_id,
			offset=offset,
			limit=SPOTIFY_REQUEST_LIMIT,
			fields="items(track(name,artists(name)))"
		)

		for item in data["items"]:

			track = item["track"]

			if track:

				track_name = track["name"]
				track_artists = ", ".join(
					artist["name"]
					for artist
					in track["artists"][:SPOTIFY_ARTISTS_LIMIT]
				)

				if track["name"] and track_artists != "":

					results.append({
						"name": track_name,
						"artists": track_artists
					})

			# end for item
		
		# end for offset

	return results

	# end

def print_local_playlists(playlists: dict) -> list:
	"""Stampa a schermo le playlist disponibili localmente e restituisce i relativi ID.

	Args:
		playlists (dict): dizionario contenente le playlist locali.

	Returns:
		list: lista degli ID delle playlist locali.
	"""

	playlist_ids = list(playlists.keys())

	for idx, (pid, value) in enumerate(playlists.items(), 1):
		print(f"{idx}. {pid} | {value['name']}")
	
	return playlist_ids
	
	# end

def get_processed_playlists(playlists: dict) -> list:
	"""Recupera e mostra le playlist che hanno già un file CSV associato.

	Args:
		playlists (dict): dizionario contenente le playlist locali.

	Returns:
		list: lista di tuple contenenti (playlist_id, csv_path, playlist_name)
	"""

	playlist_csv = [
		(pid, info["csv"], info["name"])
		for pid, info in playlists.items()
		if info.get("csv")
	]

	for i, (_, csv_path, name) in enumerate(playlist_csv, 1):
		print(f"{i}. {name}: {csv_path}")
	
	return playlist_csv

	# end

def search_youtube_video(track: dict, query_type: QueryType = QueryType.AUDIO) -> str | None:
	"""Cerca un video su YouTube e restituisce l'URL del primo risultato.

	Args:
		track (dict): dizionario che descrive la canzone da scaricare.
		query_type (QueryType): il tipo di video che si vuole scaricare. Defaults to QueryType.AUDIO.
	
	Returns:
		str: l'URL del primo risultato su Youtube.
	"""
	
	try:

		query = f"{track['name']} {track['artists']} {query_type.value}"
	
		with YoutubeDL(YOUTUBE_SEARCH_OPTIONS) as ydl:
			res = ydl.extract_info(f"ytsearch{YOUTUBE_QUERY_LIMIT}:{query}", download=False)
	
		items = res.get("entries", [])
		if not items:
			print(f"⚠️ Nessun video trovato per '{query}'.")
			return None
		
		items = [v for v in items
			if v.get("duration") \
			and v["duration"] <= YOUTUBE_DURATION_LIMIT
		]
		if not items:
			print(f"⚠️ Nessun video valido trovato per '{query}'.")
			return None
		
		video_id = items[0]['id']

		return f"https://youtu.be/{video_id}"

	except Exception as e:
		print(f"⚠️ Errore generico in 'search_youtube_video' per '{query or '?'}': {e}\n")
		return None

	# end

def process_playlist(
		sp: Spotify,
		playlist_id: str,
		playlist_name: str,
		query_type: QueryType,
		start: int,
		length: int | None = None,
		output_dir = "output"
	) -> str:
	"""Estrae le tracce da una playlist e salva i link YouTube.

	Args:
		sp (Spotify): il client Spotify.
		playlist_id (str): ID Spotify di una playlist.
		playlist_name (str): nome della playlist Spotify.
		query_type (QueryType): il tipo di video che si vuole scaricare.
		start (int): indice di inizio dell'elaborazione.
		length (int): numero di elementi da elaborare.
		output_dir (str, optional): la directory dove salvare l'output. Defaults to "output".

	Returns:
		str: il path del file CSV in output.
	"""

	os.makedirs(output_dir, exist_ok=True)

	timestamp = datetime.now().strftime("%Y.%m.%d")
	
	file_path = os.path.join(output_dir, f"{timestamp} - {playlist_name}.csv")

	print(f"\n🎧 Elaboro playlist: {playlist_name}")
	tracks = extract_playlist_tracks(sp, playlist_id)

	if length is None:
		end = len(tracks)
	else:
		end = start + length
	
	subset = tracks[start:end]

	with open(file_path, "w", encoding="utf-8", newline="") as csvfile:
		writer = csv.DictWriter(csvfile, fieldnames=["track name", "track artists", "query type", "youtube link"])
		writer.writeheader()

		for track in tqdm(subset, desc="Ricerca su YouTube"):
			youtube_link = search_youtube_video(track, query_type) or "-"

			writer.writerow({
                "track name": track["name"],
                "track artists": track["artists"],
                "query type": query_type.value,
                "youtube link": youtube_link
            })

			# Per evitare rate limit.
			time.sleep(random.uniform(0.5, 1.5))
		
			# end for track
		
		# end open csvfile
	
	return file_path

	# end

#	########################################################################	#
#	DOWNLOAD delle playlists

def download_from_csv(
	csv_file,
	playlist_name: str,
	output_dir: str = "downloads"
) -> str:
	"""Scarica MP3 o MP4 dai link presenti nel CSV in base alla colonna 'query type'.

	Args:
		csv_file (File): file CSV (colonne: track name, track artists, query type, youtube link) contenente i video da scaricare.
		playlist_name (str): nome della playlist Spotify.
		output_dir (str, optional): la directory dove salvare i download. Defaults to "downloads".
	
	Returns:
		None
	"""

	timestamp = datetime.now().strftime("%Y.%m.%d")
	output_dir = f"{output_dir}/{timestamp} - {playlist_name}"
	os.makedirs(output_dir, exist_ok=True)

	with open(csv_file, newline="", encoding="utf-8") as f:
		data = list(csv.DictReader(f))

	for row in tqdm(data, total=len(data), desc="Download da YouTube"):
		track_name = row["track name"]
		track_artists = row["track artists"]
		query = row.get("query type", "").lower()
		url = row["youtube link"]

		if not url or url == "-":
			print(f"❌ Link non trovato per {track_name}")
			continue
		
		# Genera un nome file sicuro.
		safe_name = f"{get_safename(track_name)} - {get_safename(track_artists)}"

		if query == QueryType.VIDEO.value:
			ydl_opts = YOUTUBE_DOWNLOAD_VIDEO_OPTIONS
			ydl_opts["outtmpl"] = os.path.join(output_dir, f"{safe_name}.mp4")
		elif query == QueryType.AUDIO.value:
			ydl_opts = YOUTUBE_DOWNLOAD_AUDIO_OPTIONS
			ydl_opts["outtmpl"] = os.path.join(output_dir, f"{safe_name}")
		elif query == QueryType.LYRICS.value:
			ydl_opts = YOUTUBE_DOWNLOAD_VIDEO_OPTIONS
			ydl_opts["outtmpl"] = os.path.join(output_dir, f"{safe_name}.mp4")
		elif query == QueryType.EXTENDED.value:
			ydl_opts = YOUTUBE_DOWNLOAD_AUDIO_OPTIONS
			ydl_opts["outtmpl"] = os.path.join(output_dir, f"{safe_name}")
		else:
			print(f"❌ Query non valida per {track_name}")
			continue

		with YoutubeDL(ydl_opts) as ydl:
			ydl.download([url])
		
		# end for row
	
	return output_dir

	# end

#	########################################################################	#
#	MAIN

if __name__ == '__main__':

	#	####################################################################	#
	#	INIZIALIZZAZIONE

	print("Benvenuto!\n")

	client_id, client_secret, redirect_uri = load_spotify_config()
	if not all([client_id, client_secret, redirect_uri]):
		print("Collega il tuo account Spotify.")

		client_id = input("\nInserisci il Client ID: ").strip() if not client_id else client_id
		client_secret = input("Inserisci il Client SECRET: ").strip() if not client_secret else client_secret
		redirect_uri = input("Inserisci il Redirect URI: ").strip() if not redirect_uri else redirect_uri
		print("\n")

	# Crea il client.
	sp = get_spotify_client(client_id, client_secret, redirect_uri)

	#	####################################################################	#
	#	MENU INTERATTIVO

	if sp is not None:
		print("\n🎵 Spotify2YouTube Downloader 🎵")
		print(f"{'-' * 80}")

	playlists = {}
	found_tracks = []
	selected_tracks = []

	try:
		while sp is not None:

			print("\nMenu:")
			for idx, item in enumerate(MENU_LIST, 1):
				print(f"{idx}. {item.value}")
			menu_scelta = input(f"\n👉 Seleziona un'opzione (1-{len(MENU_LIST)}): ").strip()
			
			if menu_scelta.isdigit() and 1 <= int(menu_scelta) <= len(MENU_LIST):
				menu_scelta = MENU_LIST[int(menu_scelta) - 1]

				if menu_scelta == MenuItems.CREATE_PLAYLIST:

					selected_tracks.clear()

					try:

						nome_scelto = input("👉 Inserisci un nome per la nuova playlist: ").strip()
						if not nome_scelto:
							print("❌ Nome playlist non valido.")
							continue

						print("\n🎵 Cerca i brani da aggiungere.\n")

						while True:

							found_tracks.clear()

							query = input("🔍 Inserisci il nome di una canzone (premi Ctrl + C per terminare): ").strip()
							if not query:
								print("❌ Query non valida.")
								continue

							found_tracks = search_spotify_tracks(sp, query)
							if not found_tracks:
								print("❌ Nessun risultato trovato.")
								continue

							track_scelta = input("\n👉 Inserisci il numero del brano da aggiungere (premi Invio per saltare): ").strip()
							if track_scelta.isdigit() and 1 <= int(track_scelta) <= len(found_tracks):
								
								track_scelta = int(track_scelta) - 1
								
								selected_tracks.append(found_tracks[track_scelta]["id"])
								print(f"\n✅ Aggiunto: {found_tracks[track_scelta]['name']} — {found_tracks[track_scelta]['artists']}\n")
							
							else:
								print("⚠️ Nessun brano aggiunto.\n")
								continue
						
						# end while
					
					except KeyboardInterrupt:

						print("\n🆗 Inserimento terminato manualmente.\n")

						if not selected_tracks:
							print("⚠️ Nessuna traccia selezionata. Playlist non creata.")
							continue

						playlist_id = upload_spotify_playlist(sp, nome_scelto, selected_tracks)
						if not playlist_id:
							continue

						playlist_name = get_safename(nome_scelto)

						playlists[playlist_id] = {"name": playlist_name}
						
						print(f"\n✅ Playlist aggiunta: {playlist_id} | {nome_scelto}")

					# end try

				elif menu_scelta == MenuItems.ADD_PLAYLIST:

					url = input("👉 Inserisci URL della playlist Spotify: ").strip()

					playlist_id = get_playlist_id_from_url(url)
					if not playlist_id:
						print("❌ Playlist ID non valido.\n")
						continue

					playlist_info = sp.playlist(playlist_id)
					playlists[playlist_id] = {"name": get_safename(playlist_info['name'])}
					
					print(f"\n✅ Playlist aggiunta: {playlist_id} | {playlist_info['name']}")

				elif menu_scelta == MenuItems.PRINT_PLAYLIST:

					if not playlists:
						print("⚠️ Nessuna playlist inserita.")
						continue

					print("🎧 Playlist inserite:")
					print_local_playlists(playlists)

				elif menu_scelta == MenuItems.PROCESS_PLAYLIST:

					if not playlists:
						print("⚠️ Nessuna playlist da elaborare.")
						continue

					print("\n🎧 Playlist inserite:")
					playlist_ids = print_local_playlists(playlists)
					playlist_scelta = input(f"\n👉 Seleziona un'opzione (1-{len(playlists)}): ").strip()

					if not playlist_scelta.isdigit():
						print("❌ Opzione non valida.")
						continue

					playlist_scelta = int(playlist_scelta)
					if not 1 <= playlist_scelta <= len(playlists):
						print("❌ Opzione non valida.")
						continue

					playlist_scelta = playlist_ids[playlist_scelta - 1]
					
					dir_scelta = input("👉 Inserisci la cartella di output (default: 'output'): ").strip() or "output"

					print("👉 Inserisci il tipo di query:")
					for idx, query in enumerate(QUERY_LIST, 1):
						print(f"{idx}. {query}")
					query_scelta = input(f"\n👉 Seleziona un'opzione (1-{len(QUERY_LIST)}): ").strip()
					
					if not query_scelta.isdigit():
						print("❌ Opzione non valida.")
						continue

					query_scelta = int(query_scelta)
					if not 1 <= query_scelta <= len(QUERY_LIST):
						print("❌ Opzione non valida.")
						continue

					playlist_info = playlists[playlist_scelta]
					if not playlist_info:
						print("❌ Playlist non valida.")
						continue
						
					csv_path = process_playlist(
						sp,
						playlist_id = playlist_scelta,
						playlist_name = playlist_info["name"],
						query_type = QUERY_LIST[query_scelta-1],
						start = 0, length = None,
						output_dir = dir_scelta
					)

					playlists[playlist_scelta].update({"csv": csv_path})
					print(f"✅ File salvato in: {csv_path}")

					print("✅ Elaborazione completata.")

				elif menu_scelta == MenuItems.DOWNLOAD_PLAYLIST:

					if not playlists or all(not data.get("csv") for data in playlists.values()):
						print("⚠️ Nessun file CSV generato in questa sessione.")
						scelta_csv = input("👉 Inserisci il percorso del file CSV: ").strip()

						if not scelta_csv:
							print("❌ Nessun file fornito.\n")
							continue
						
						csv_file = scelta_csv
						playlist_name = os.path.splitext(os.path.basename(csv_file))[0]

					else:
						print("\n🎧 Playlist elaborate:")
						playlist_csv = get_processed_playlists(playlists)
						scelta_csv = input(f"\n👉 Seleziona un'opzione (1-{len(playlist_csv)}): ").strip()

						if not scelta_csv.isdigit():
							print("❌ Opzione non valida.")
							continue

						scelta_csv = int(scelta_csv)
						if not 1 <= scelta_csv <= len(playlist_csv):
							print("❌ Opzione non valida.")
							continue

						_, csv_file, playlist_name = playlist_csv[scelta_csv-1]
					
					# end if

					if not os.path.exists(csv_file):
						print(f"❌ Il file '{csv_file}' non esiste.\n")
						continue

					dir_scelta = input("👉 Inserisci la cartella di download (default: 'downloads'): ").strip() or "downloads"

					try:
						print(f"\n🎵 Avvio download per '{playlist_name}'...")

						download_path = download_from_csv(
							csv_file,
							playlist_name,
							output_dir=dir_scelta
						)

						print(f"✅ Media salvati in: {download_path}")
						print("✅ Elaborazione completata.")

					except Exception as e:
						print(f"❌ Errore durante il download: {e}\n")

				elif menu_scelta == MenuItems.EXIT:
					print('Interruzione in corso...')
					break

				else:
					print("❌ Opzione non valida.")
					continue

			else:
				print("❌ Opzione non valida.")
				continue

	except KeyboardInterrupt:
		pass

	#	####################################################################	#
	#	CHIUSURA
	
	print('\n\n👋 Arrivederci!')
	exit(0)

	# end