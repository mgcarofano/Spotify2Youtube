"""

	functions.py
	di Mario Gabriele Carofano

	Modulo contenente funzioni per l'interazione con Spotify e YouTube.

"""

#	########################################################################	#
#	LIBRERIE

from datetime import datetime
import random
import time
import tempfile

import pandas as pd

from yt_dlp import YoutubeDL
from ytmusicapi import YTMusic

from utilities import *

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
			fields="items(track(name,artists(name),duration_ms))"
		)

		for item in data["items"]:

			track = item["track"]

			if not track:
				print("⚠️ Traccia non valida.")
				continue

			track_name = track["name"]
			if not track_name:
				print("⚠️ Nome della traccia non trovato.")
				continue
			
			track_artists = ", ".join(
				artist["name"]
				for artist
				in track["artists"][:SPOTIFY_ARTISTS_LIMIT]
			)
			if track_artists == "":
				print("⚠️ Nomi degli artisti non trovati.")
				continue
			
			track_duration = track["duration_ms"]
			if not track_duration or track_duration <= 0:
				print("⚠️ Durata della traccia non trovata.")
				continue

			results.append({
				"name": track_name,
				"artists": track_artists,
				"duration": track_duration // 1000
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

def search_from_youtube(
		ytmusic: YTMusic,
		track: dict,
		query_type: QueryType = QueryType.AUDIO
	) -> list[dict] | None:
	"""Cerca risultati YouTube e restituisce i metadati di quelli che superano i filtri.

	Args:
		ytmusic (YTMusic): client YTMusic.
		track (dict): dizionario che descrive la canzone da scaricare.
		query_type (QueryType, optional): il tipo di video che si vuole scaricare. Defaults to QueryType.AUDIO.

	Returns:
		list[dict] | None: lista dei risultati validi su YouTube.
	"""

	query = f"{track['name']} {track['artists']} {query_type.value}"
	print(f"🔍 Query: '{query}'")

	initial_limit = max(1, YOUTUBE_QUERY_LIMIT)
	current_limit = initial_limit
	max_results = max(initial_limit, MAX_YOUTUBE_RESULTS)
	seen_ids = set()
	ret = []
	items = []

	while not ret:

		if query_type in [QueryType.AUDIO, QueryType.EXTENDED]:

			try:
				items = [
					normalize_result(v, "videoId")
					for v in ytmusic.search(
						query,
						filter="songs",
						limit=current_limit
					)
				]
			except Exception as e:
				print(f"⚠️ Errore generico in 'search_from_youtube': {e}\n")

		elif query_type in [QueryType.VIDEO, QueryType.LYRICS]:

			try:
				with YoutubeDL(YOUTUBE_SEARCH_OPTIONS) as ydl:
					res = ydl.extract_info(
						f"ytsearch{current_limit}:{query}",
						download=False
					)

				items = [
					normalize_result(v, "id")
					for v in res.get("entries", [])
					if v
				]
			except Exception as e:
				print(f"⚠️ Errore generico in 'search_from_youtube': {e}\n")

		else:
			raise ValueError("QueryType non valido.")
		
		# end if query_type
		
		if not items:
			print(f"⚠️ Nessun altro risultato trovato per '{query}'.")
			break

		# La ricerca ampliata include anche i risultati già visti
		# ma considera soltanto gli ID nuovi.
		new_items = []
		for v in items:
			video_id = v.get("id")
			if video_id and video_id not in seen_ids:
				seen_ids.add(video_id)
				new_items.append(v)

		# Se l'API non restituisce risultati nuovi, non c'è altro da esaminare.
		if not new_items:
			print(f"⚠️ Nessun nuovo risultato trovato per '{query}'.")
			break
		
		for v in new_items:
			v_id = v.get('id')
			v_duration = v.get('duration')

			if not v_id or not v_duration:
				print(f"⚠️ Scartato. ID o durata mancante: {v}")
				continue

			if v_duration > YOUTUBE_DURATION_LIMIT:
				print(f"⚠️ Scartato. Durata eccessiva: {v_duration} secondi")
				continue

			s_duration = track.get("duration", 0)
			if abs(s_duration - v_duration) > YOUTUBE_MARGIN_SECONDS:
				print(f"⚠️ Scartato. Durata su Youtube ({v_duration}) non compatibile rispetto alla traccia su Spotify ({s_duration}).")
				continue

			if query_type == QueryType.EXTENDED:
				v_title = (v.get("title") or "").lower()

				if any(k in v_title for k in YOUTUBE_EXTENDED_EXCLUDED_KEYWORDS):
					continue

				if not any(k in v_title for k in YOUTUBE_EXTENDED_INCLUDED_KEYWORDS):
					continue

			ret.append({
				"url": f"https://youtu.be/{v_id}",
				"channel": v.get("channel"),
				"original_title": v.get("title"),
			})

		# end for v

		if current_limit >= max_results:
			print(f"⚠️ Limite massimo di risultati raggiunto ({current_limit}).")
			break

		current_limit = min(current_limit + YOUTUBE_QUERY_LIMIT, max_results)
	
	# end while

	if ret:
		print(f"✅ Trovati {len(ret)} risultati validi.")
		return ret

	print(f"⚠️ Nessun risultato valido trovato per '{query}'.")
	return None

	# end

def process_playlist(
		sp: Spotify,
		yt_music: YTMusic,
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
		yt_music (YTMusic): il client Youtube.
		playlist_id (str): ID Spotify di una playlist.
		playlist_name (str): nome della playlist Spotify.
		query_type (QueryType): il tipo di video che si vuole scaricare.
		start (int): indice di inizio dell'elaborazione.
		length (int): numero di elementi da elaborare.
		output_dir (str, optional): la directory dove salvare l'output. Defaults to "output".

	Returns:
		str: il path del file CSV in output.
	"""

	timestamp = datetime.now().strftime("%Y.%m.%d")
	out_dir = Path(output_dir) / f"{timestamp}"
	out_dir.mkdir(parents=True, exist_ok=True)

	file_path = out_dir / f"{playlist_name}_{(query_type.name).lower()}.csv"

	print(f"\n🎧 Elaboro playlist: {playlist_name}")
	tracks = extract_playlist_tracks(sp, playlist_id)

	if length is None:
		end = len(tracks)
	else:
		end = start + length
	
	subset = tracks[start:end]
	# print(f"\n\nSubset: {subset}\n\n")

	rows = []

	for i, track in enumerate(subset):
		print(f"\n🔍 Ricerca su YouTube per la traccia {i+1}/{len(subset)}")
		yt_data = search_from_youtube(yt_music, track, query_type) or []

		# Salva una riga per ogni risultato di ricerca.
		# Se non ci sono dati da youtube, salva comunque una riga vuota.
		results = yt_data or [{}]

		for r in results:
			rows.append({
			"track name": track["name"],
			"track artists": track["artists"],
			"query type": query_type.value,
			"youtube link": r.get("url", ""),
			"original title": r.get("original_title", ""),
			"youtube channel": r.get("channel", ""),
		})

		# Per evitare rate limit.
		time.sleep(random.uniform(0.5, 1.5))

		pd.DataFrame(
			rows,
			columns=[
				"track name",
				"track artists",
				"query type",
				"youtube link",
				"original title",
				"youtube channel",
			],
		).to_csv(file_path, index=False, encoding="utf-8")

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
		str: il percorso della directory dei download.
	"""

	timestamp = datetime.now().strftime("%Y.%m.%d")
	output_path = Path(output_dir) / (f"{timestamp} - {playlist_name}")
	output_path.mkdir(parents=True, exist_ok=True)

	data = pd.read_csv(csv_file).fillna("")
	group_columns = ["track name", "track artists", "query type"]
	grouped = data.groupby(group_columns, sort=False, dropna=False)

	for i, ((track_name, track_artists, query), group) in enumerate(grouped):

		print(f"\n⏳ Elaborazione della traccia {i+1}/{grouped.ngroups}")
		
		track_name = str(track_name)
		track_artists = str(track_artists)

		# Genera un nome file sicuro.
		safe_name = (
            f"{get_safename(track_name)} - "
            f"{get_safename(track_artists)}"
        )

		query = str(query).strip().lower()

		# Nel CSV ogni riga contiene un singolo risultato.
		# Raccoglie URL e metadati, eliminando URL vuoti o duplicati.
		results = []
		seen_urls = set()

		for url, channel, title in group[
			["youtube link", "youtube channel", "original title"]
		].itertuples(index=False, name=None):
			url = str(url).strip()
			if not url or url == "-" or url in seen_urls:
				continue

			seen_urls.add(url)
			results.append((url, str(channel).strip(), str(title).strip()))

		if not results:
			print(f"❌ Link non trovato per {track_name}")
			continue

		url_scelto = None

		while True:
			try:
				while url_scelto is None:
					print(f"🔎 Trovati {len(results)} risultati per {track_name}:")
					for index, (url, channel, title) in enumerate(results, start=1):
						print(
							f"{index}.\t{url}"
							f" | {channel or 'N/D'}"
							f" | {title or 'N/D'}"
						)

					choice = input(f"\n👉 Seleziona il link da scaricare (1-{len(results)}): ").strip()
					if choice.isdigit() and 1 <= int(choice) <= len(results):
						url_scelto = results[int(choice) - 1][0]
					else:
						print("❌ Opzione non valida.")

			except KeyboardInterrupt:
				print(f"\n⏭️  Selezione annullata: {track_name}")
				break

			try:

				if query in {QueryType.VIDEO.value, QueryType.LYRICS.value}:

					with tempfile.TemporaryDirectory(
						prefix="youtube_download_"
					) as temp_dir:

						ydl_opts = YOUTUBE_DOWNLOAD_VIDEO_OPTIONS.copy()
						ydl_opts["outtmpl"] = str(
							Path(temp_dir) / "%(id)s.%(ext)s"
						)

						with YoutubeDL(ydl_opts) as ydl:
							ydl.download([url_scelto])

						# Individua inline il file MKV generato da yt-dlp.
						source_file = next(
							Path(temp_dir).glob("*.mkv"),
							None,
						)

						if source_file is None:
							raise FileNotFoundError(
								"yt-dlp non ha generato il file MKV."
							)

						print(f"✅ Download temporaneo completato.")

						convert_video(
							input_file=source_file,
							output_file=output_path / f"{safe_name}.mp4",
						)

					print(f"✅ Video completato: {safe_name}")

				elif query in {QueryType.AUDIO.value, QueryType.EXTENDED.value}:

					ydl_opts = YOUTUBE_DOWNLOAD_AUDIO_OPTIONS.copy()
					ydl_opts["outtmpl"] = str(output_path / f"{safe_name}.%(ext)s")

					with YoutubeDL(ydl_opts) as ydl:
						ydl.download([url_scelto])

					print(f"✅ Audio completato: {safe_name}")

				# else:
				# 	print(f"❌ Query non valida per {track_name}")

			except subprocess.CalledProcessError as e:
				print(
					f"❌ Conversione FFmpeg fallita per {track_name}: "
					f"codice {e.returncode}"
				)
				continue

			except Exception as e:
				print(f"❌ Errore durante il download di {track_name}: {e}")
				print("Riprova con un altro link.")
				url_scelto = None
				continue

			break

			# end while
		
		# end for row
	
	return str(output_path)

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

	# Crea il client Spotify.
	sp = get_spotify_client(client_id, client_secret, redirect_uri)

	# Crea il client Youtube.
	yt_music = YTMusic()

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

				if menu_scelta == MenuItems.PRINT_PLAYLIST:

					if not playlists:
						print("⚠️ Nessuna playlist inserita.")
						continue

					print("\n🎧 Playlist inserite:")
					print_local_playlists(playlists)

				elif menu_scelta == MenuItems.PROCESS_PLAYLIST:

					url = input("👉 Inserisci URL della playlist Spotify: ").strip()

					playlist_id = get_playlist_id_from_url(url)
					if not playlist_id:
						print("❌ Playlist ID non valido.\n")
						continue

					playlist_info = sp.playlist(playlist_id)
					playlists[playlist_id] = {"name": get_safename(playlist_info['name'])}
					
					print(f"\n✅ Playlist aggiunta: {playlist_id} | {playlist_info['name']}")

					# if not playlists:
					# 	print("⚠️ Nessuna playlist da elaborare.")
					# 	continue

					# print("\n🎧 Playlist inserite:")
					# playlist_ids = print_local_playlists(playlists)
					# playlist_scelta = input(f"\n👉 Seleziona un'opzione (1-{len(playlists)}): ").strip()

					# if not playlist_scelta.isdigit():
					# 	print("❌ Opzione non valida.")
					# 	continue

					# playlist_scelta = int(playlist_scelta)
					# if not 1 <= playlist_scelta <= len(playlists):
					# 	print("❌ Opzione non valida.")
					# 	continue

					# playlist_scelta = playlist_ids[playlist_scelta - 1]
					
					dir_scelta = input("\n👉 Inserisci la cartella di output (default: 'output'): ") \
						.strip() \
						.strip("\"") \
						.strip("\'") \
						or "output"

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

					# playlist_info = playlists[playlist_scelta]
					# if not playlist_info:
					# 	print("❌ Playlist non valida.")
					# 	continue
						
					csv_path = process_playlist(
						sp, yt_music,
						playlist_id = playlist_id,
						playlist_name = playlist_info["name"],
						query_type = QUERY_LIST[query_scelta-1],
						start = 0, length = None,
						output_dir = dir_scelta
					)

					playlists[playlist_id].update({"csv": csv_path})
					print(f"✅ File salvato in: {csv_path}")

					print("✅ Elaborazione completata.")

				elif menu_scelta == MenuItems.DOWNLOAD_PLAYLIST:

					if not playlists or all(not data.get("csv") for data in playlists.values()):
						print("\n⚠️ Nessun file CSV generato in questa sessione.")
						scelta_csv = input("👉 Inserisci il percorso del file CSV: ") \
							.strip() \
							.strip("\"") \
							.strip("\'")

						if not scelta_csv:
							print("❌ Nessun file fornito.\n")
							continue
						
						csv_file = scelta_csv
						playlist_name = Path(csv_file).stem

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

					if not Path(csv_file).exists():
						print(f"❌ Il file '{csv_file}' non esiste.\n")
						continue

					dir_scelta = input("👉 Inserisci la cartella di download (default: 'downloads'): ") \
						.strip() \
						.strip("\"") \
						.strip("\'") \
						or "downloads"

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
		print('\nInterruzione in corso...')
		pass

	#	####################################################################	#
	#	CHIUSURA
	
	print('\n\n👋 Arrivederci!')
	exit(0)

	# end
