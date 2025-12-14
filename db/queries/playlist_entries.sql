-- name: ListPlaylistEntries :many
SELECT * FROM playlist_entries 
WHERE playlist_id = $1 
ORDER BY position, added_at;

-- name: GetPlaylistEntry :one
SELECT * FROM playlist_entries WHERE id = $1;

-- name: GetPlaylistEntryByInput :one
SELECT * FROM playlist_entries 
WHERE playlist_id = $1 AND original_input = $2;

-- name: AddPlaylistEntry :one
INSERT INTO playlist_entries (
    playlist_id, 
    original_input, 
    source_type, 
    title, 
    duration_seconds,
    thumbnail_url,
    position, 
    added_by
)
VALUES (
    $1, 
    $2, 
    $3, 
    $4, 
    $5,
    $6,
    COALESCE(
        (SELECT MAX(position) + 1 FROM playlist_entries WHERE playlist_id = $1),
        0
    ),
    $7
)
RETURNING *;

-- name: UpdatePlaylistEntry :one
UPDATE playlist_entries
SET title = COALESCE(sqlc.narg('title'), title),
    duration_seconds = COALESCE(sqlc.narg('duration_seconds'), duration_seconds),
    thumbnail_url = COALESCE(sqlc.narg('thumbnail_url'), thumbnail_url)
WHERE id = $1
RETURNING *;

-- name: DeletePlaylistEntry :exec
DELETE FROM playlist_entries WHERE id = $1;

-- name: DeletePlaylistEntryByInput :exec
DELETE FROM playlist_entries 
WHERE playlist_id = $1 AND original_input = $2;

-- name: DeletePlaylistEntriesByPlaylistID :exec
DELETE FROM playlist_entries WHERE playlist_id = $1;

-- name: CountPlaylistEntries :one
SELECT COUNT(*)::int FROM playlist_entries WHERE playlist_id = $1;

-- name: EntryExistsInPlaylist :one
SELECT EXISTS(
    SELECT 1 FROM playlist_entries 
    WHERE playlist_id = $1 AND original_input = $2
);

-- name: ReorderPlaylistEntry :exec
UPDATE playlist_entries SET position = $2 WHERE id = $1;

-- name: GetPlaylistWithEntries :many
SELECT 
    p.id AS playlist_id,
    p.name AS playlist_name,
    p.guild_id,
    p.created_at AS playlist_created_at,
    pe.id AS entry_id,
    pe.original_input,
    pe.source_type,
    pe.title,
    pe.duration_seconds,
    pe.position,
    pe.added_at AS entry_added_at
FROM playlists p
LEFT JOIN playlist_entries pe ON p.id = pe.playlist_id
WHERE p.name = $1 AND (p.guild_id = sqlc.narg('guild_id') OR p.guild_id IS NULL)
ORDER BY pe.position, pe.added_at;
