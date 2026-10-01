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
import tempfile
from urllib.error import HTTPError

import pandas as pd
from tqdm import tqdm

from yt_dlp import YoutubeDL
from ytmusicapi import YTMusic

from utilities import *

#	########################################################################	#
#	CREAZIONE e MODIFICA delle playlist

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

	# def normalize_result(raw: dict, id_key: str) -> dict:
	# 	item = normalize_ytmusic_item(raw, id_key)
	# 	item["title"] = raw.get("title") or item.get("title")
	# 	item["channel"] = (
	# 		raw.get("channel")
	# 		or raw.get("uploader")
	# 		or raw.get("channel_name")
	# 	)
	# 	return item

	# 	# end normalize_result

	query = f"{track['name']} {track['artists']} {query_type.value}"
	print(f"\n🔍 Ricerca su YouTube per: '{query}'")

	initial_limit = max(1, YOUTUBE_QUERY_LIMIT)
	current_limit = initial_limit
	max_results = max(initial_limit, MAX_YOUTUBE_RESULTS)
	seen_ids = set()
	ret = []

	try:
		while not ret:

			if query_type in [QueryType.AUDIO, QueryType.EXTENDED]:

				items = [
					normalize_result(v, "videoId")
					for v in ytmusic.search(
						query,
						filter="songs",
						limit=current_limit
					)
				]

			elif query_type in [QueryType.VIDEO, QueryType.LYRICS]:

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

			else:

				raise ValueError("QueryType non valido.")
			
			# end if query_type
			
			if not items:
				print(f"⚠️ Nessun altro risultato trovato per '{query}'.")
				break

			# La ricerca ampliata include anche i risultati già visti:
			# considera soltanto gli ID nuovi.

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

			if ret or current_limit >= max_results:
				print(f"⚠️ Limite massimo di risultati raggiunto ({current_limit}).")
				break

			current_limit = min(current_limit + YOUTUBE_QUERY_LIMIT, max_results)
		
		# end while

		if ret:
			return ret

		print(f"⚠️ Nessun risultato valido trovato per '{query}'.")
		return None

	except Exception as e:
		print(
			f"⚠️ Errore generico in 'search_from_youtube' "
		    f"per '{query or '?'}': {e}\n"
		)
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

	out_dir = Path(output_dir)
	out_dir.mkdir(parents=True, exist_ok=True)

	timestamp = datetime.now().strftime("%Y.%m.%d")
	file_path = out_dir / f"{timestamp} - {playlist_name}_{(query_type.name).lower()}.csv"

	print(f"\n🎧 Elaboro playlist: {playlist_name}")
	tracks = extract_playlist_tracks(sp, playlist_id)

	if length is None:
		end = len(tracks)
	else:
		end = start + length
	
	subset = tracks[start:end]

	# print(f"\n\nSubset: {subset}\n\n")

	# with open(file_path, "w", encoding="utf-8", newline="") as csvfile:
	# 	writer = csv.DictWriter(
	# 		csvfile,
	# 		fieldnames=[
	# 			"track name",
	# 			"track artists",
	# 			"query type",
	# 			"youtube links",
	# 			"original title",
	# 			"youtube channel",
	# 		],
	# 	)
	# 	writer.writeheader()

	# 	for track in tqdm(subset, desc="Ricerca su YouTube"):
	# 		yt_data = search_from_youtube(yt_music, track, query_type) or []

	# 		writer.writerow({
    #             "track name": track["name"],
    #             "track artists": track["artists"],
    #             "query type": query_type.value,
    #             "youtube links": json.dumps(
	# 				[result["url"] for result in yt_data if result.get("url")],
	# 				ensure_ascii=False,
	# 			),
	# 			"original titles": json.dumps(
	# 				[result.get("original_title") for result in yt_data],
	# 				ensure_ascii=False,
	# 			),
	# 			"youtube channels": json.dumps(
	# 				[result.get("channel") for result in yt_data],
	# 				ensure_ascii=False,
	# 			),
    #         })

	# 		# Per evitare rate limit.
	# 		time.sleep(random.uniform(0.5, 1.5))
		
	# 		# end for track
		
	# 	# end open csvfile
	
	# return file_path

	rows = []

	for track in tqdm(subset, desc="Ricerca su YouTube"):
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

	# with open(csv_file, newline="", encoding="utf-8") as f:
	# 	data = list(csv.DictReader(f))

	# for row in tqdm(data, total=len(data), desc="Download da YouTube"):
	# 	# Si resetta l'URL scelto per ogni traccia.
	# 	url_scelto = None
	# 	choice = None

	# 	track_name = row["track name"]
	# 	track_artists = row["track artists"]
	# 	query = row.get("query type", "").lower()
	# 	raw_urls = row.get("youtube links", "")

	# 	if not raw_urls or raw_urls == "-":
	# 		print(f"❌ Link non trovato per {track_name}")
	# 		continue

	# 	raw_urls = json.loads(raw_urls.replace('\'', '"'))

	data = pd.read_csv(csv_file).fillna("")
	group_columns = ["track name", "track artists", "query type"]

	for (track_name, track_artists, query), group in tqdm(
        data.groupby(group_columns, sort=False, dropna=False),
        total=data.groupby(group_columns, sort=False, dropna=False).ngroups,
        desc="Download da YouTube",
    ):

		track_name = str(track_name)
		track_artists = str(track_artists)
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
		try:
			while url_scelto is None:
				print(f"\n🔎 Trovati {len(results)} risultati per {track_name}:")
				for index, (url, channel, title) in enumerate(results, start=1):
					print(
						f"{index}.\t{url}"
						f" | {channel or 'N/D'}"
						f" | {title or 'N/D'}"
					)

				choice = input(f"Seleziona il link da scaricare (1-{len(results)}): ").strip()
				if choice.isdigit() and 1 <= int(choice) <= len(results):
					url_scelto = results[int(choice) - 1][0]
				else:
					print("❌ Opzione non valida.")

		except KeyboardInterrupt:
			print(f"\n⏭️ Selezione annullata: {track_name}")
			continue
		
		# Genera un nome file sicuro.
		safe_name = (
            f"{get_safename(track_name)} - "
            f"{get_safename(track_artists)}"
        )

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

			else:
				print(f"❌ Query non valida per {track_name}")

		except subprocess.CalledProcessError as e:
			print(
				f"❌ Conversione FFmpeg fallita per {track_name}: "
				f"codice {e.returncode}"
			)

		except HTTPError as e:
			print(f"❌ Errore HTTP ({e.code}) durante il download di {track_name}: {e}")
			print("Riprova con un altro link.")

		except Exception as e:
			print(f"❌ Errore durante il download di {track_name}: {e}")
		
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

					# end try

					playlist_id = upload_spotify_playlist(sp, nome_scelto, selected_tracks)
					if not playlist_id:
						continue

					playlist_name = get_safename(nome_scelto)

					playlists[playlist_id] = {"name": playlist_name}
					
					print(f"\n✅ Playlist aggiunta: {playlist_id} | {nome_scelto}")

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

					print("\n🎧 Playlist inserite:")
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
					
					dir_scelta = input("👉 Inserisci la cartella di output (default: 'output'): ") \
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

					playlist_info = playlists[playlist_scelta]
					if not playlist_info:
						print("❌ Playlist non valida.")
						continue
						
					csv_path = process_playlist(
						sp, yt_music,
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