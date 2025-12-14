-- name: ListPlaylists :many
-- List all playlists, optionally filtered by guild
SELECT 
    p.id,
    p.guild_id,
    p.name,
    p.description,
    p.is_public,
    p.created_by,
    p.created_at,
    p.updated_at,
    COUNT(pe.id)::int AS entry_count
FROM playlists p
LEFT JOIN playlist_entries pe ON p.id = pe.playlist_id
WHERE p.guild_id = sqlc.narg('guild_id') OR sqlc.narg('guild_id') IS NULL
GROUP BY p.id
ORDER BY p.name;

-- name: ListPlaylistsByGuild :many
SELECT 
    p.id,
    p.guild_id,
    p.name,
    p.description,
    p.is_public,
    p.created_by,
    p.created_at,
    p.updated_at,
    COUNT(pe.id)::int AS entry_count
FROM playlists p
LEFT JOIN playlist_entries pe ON p.id = pe.playlist_id
WHERE p.guild_id = $1 OR p.guild_id IS NULL
GROUP BY p.id
ORDER BY p.name;

-- name: GetPlaylistByID :one
SELECT * FROM playlists WHERE id = $1;

-- name: GetPlaylistByName :one
SELECT * FROM playlists 
WHERE name = $1 AND (guild_id = sqlc.narg('guild_id') OR guild_id IS NULL)
LIMIT 1;

-- name: GetPlaylistByNameAndGuild :one
SELECT * FROM playlists 
WHERE name = $1 AND (guild_id = $2 OR guild_id IS NULL)
ORDER BY guild_id NULLS LAST
LIMIT 1;

-- name: CreatePlaylist :one
INSERT INTO playlists (guild_id, name, description, is_public, created_by)
VALUES ($1, $2, $3, $4, $5)
RETURNING *;

-- name: UpdatePlaylist :one
UPDATE playlists
SET name = COALESCE(sqlc.narg('name'), name),
    description = COALESCE(sqlc.narg('description'), description),
    is_public = COALESCE(sqlc.narg('is_public'), is_public)
WHERE id = $1
RETURNING *;

-- name: UpdatePlaylistName :exec
UPDATE playlists
SET name = $2, updated_at = NOW()
WHERE id = $1;

-- name: DeletePlaylist :exec
DELETE FROM playlists WHERE id = $1;

-- name: DeletePlaylistByName :exec
DELETE FROM playlists 
WHERE name = $1 AND (guild_id = sqlc.narg('guild_id') OR guild_id IS NULL);

-- name: PlaylistExists :one
SELECT EXISTS(
    SELECT 1 FROM playlists 
    WHERE name = $1 AND (guild_id = sqlc.narg('guild_id') OR guild_id IS NULL)
);
