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