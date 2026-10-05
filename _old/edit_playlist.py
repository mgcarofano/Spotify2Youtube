def create_playlist_by_bpm(
	sp: Spotify,
	playlist_id: str,
	ranges: list[tuple[int, int]],
	base_name: str
) -> list[str] | None:
	
	bpm_groups = {f"{r[0]}-{r[1]}": [] for r in ranges}

	results = []
	track_ids = []
	features = []

	try:

		user_id = sp.current_user()["id"]
		playlist = sp.playlist(playlist_id)
		total_tracks = playlist["tracks"]["total"]

		for offset in range(0, total_tracks, SPOTIFY_REQUEST_LIMIT):
			
			# Si estraggono i dati di 'limit' brani dalla playlist.
			data = sp.playlist_tracks(
				playlist_id,
				offset=offset,
				limit=SPOTIFY_REQUEST_LIMIT,
				fields="items.track.id"
			)

			track_ids.extend([item["track"]["id"] for item in data["items"] if item["track"]])
			
			# end for offset

		print(f"Trovati {len(track_ids)} brani.")

		# Recupera le audio features di una lista di brani.
		# In blocchi da 100 per evitare "Error 414: URI Too Long".
		for i in range(0, len(track_ids), SPOTIFY_REQUEST_LIMIT):
			print(f"Elaborazione blocco {i}-{i+SPOTIFY_REQUEST_LIMIT}")
			chunk = track_ids[i:i+SPOTIFY_REQUEST_LIMIT]
			f = sp.audio_features(chunk)
			if f:
				features.extend(f)
		
		# Rimuove eventuali None
		features = [f for f in features if f]

		for f in features:
			if not f:
				continue
			bpm = f["tempo"]
			for r in ranges:
				if r[0] <= bpm < r[1]:
					bpm_groups[f"{r[0]}-{r[1]}"].append(f["id"])
					break
				# end for r
			# end for f
		
		for label, tracks in bpm_groups.items():
			
			if not tracks:
				continue

			playlist_name = f"{base_name} [{label} BPM]"
			new_playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=False)
			
			playlist_id = new_playlist["id"]
			sp.playlist_add_items(playlist_id, tracks)
			results.append(playlist_id)

			print(f"\n✅ Playlist aggiunta: {playlist_id} | {playlist_name} | {len(tracks)} brani")

			# end for label, tracks

	except Exception as e:
		print(f"❌ Errore durante la creazione della playlist: {e}")
		return None
	
	return results

	# end

if __name__ == '__main__':

	elif menu_scelta == MenuItems.EDIT_PLAYLIST:

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
		playlist_info = playlists[playlist_scelta]
		if not playlist_info:
			print("❌ Playlist non valida.")
			continue

		print("👉 Inserisci il valore di BPM di separazione (premi Ctrl + C per terminare):")
		bpm_scelto = []
		cont = 1

		try:

			bpm_scelto.clear()
			
			while True:
				bpm_input = input(f"Valore {cont}: ").strip()
				
				if not bpm_input.isdigit():
					print("❌ Valore non valido.")
					continue

				bpm_scelto.append(int(bpm_input))
				cont = cont + 1

				# end while

		except KeyboardInterrupt:

			print("\n🆗 Inserimento terminato manualmente.\n")
			if not bpm_scelto:
				print("⚠️ Nessun valore selezionato.")
				continue

		# end try

		bpm_scelto = [0] + sorted(set(x for x in bpm_scelto)) + [float('inf')]
		ranges = [(bpm_scelto[i], bpm_scelto[i+1]) for i in range(len(bpm_scelto)-1)]

		# # Stampa formattata
		# for r in ranges:
		# 	if r[1] == float('inf'):
		# 		print(f"{r[0]}+ BPM")
		# 	else:
		# 		print(f"{r[0]} - {r[1]} BPM")

		create_playlist_by_bpm(sp, playlist_scelta, ranges, playlist_info["name"])

		print("✅ Elaborazione completata.")

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

"""

## 5. Creazione Nuova Playlist Spotify

Replica la logica di `MenuItems.CREATE_PLAYLIST`:
1. Richiede il nome della nuova playlist.
2. Permette la ricerca iterativa di brani con `search_spotify_tracks()`.
3. Consente la selezione interattiva dei risultati trovati.
4. Crea la playlist su Spotify con `upload_spotify_playlist()`.
5. Aggiorna il dizionario `playlists`.

⚠️ Esegui questa cella solo se vuoi creare una nuova playlist. Premi `Ctrl+C` (interrompi kernel) per terminare la ricerca brani.

"""

selected_tracks.clear()

try:

	nome_scelto = input("👉 Inserisci un nome per la nuova playlist: ").strip()

	if not nome_scelto:
		print("❌ Nome playlist non valido.")
	else:
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
	else:
		playlist_id = upload_spotify_playlist(sp, nome_scelto, selected_tracks)

		if playlist_id:
			playlist_name = get_safename(nome_scelto)
			playlists[playlist_id] = {"name": playlist_name}
			print(f"\n✅ Playlist aggiunta: {playlist_id} | {nome_scelto}")
