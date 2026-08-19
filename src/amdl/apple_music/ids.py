def is_library_album(album_id: str) -> bool:
    return album_id.startswith("l.")


def is_library_track(track_id: str) -> bool:
    return track_id.startswith("i.")
