-- name: GetActivePlaylist :one
SELECT 
    ap.guild_id,
    ap.playlist_id,
    ap.activated_at,
    ap.activated_by,
    p.name AS playlist_name
FROM active_playlists ap
LEFT JOIN playlists p ON ap.playlist_id = p.id
WHERE ap.guild_id = $1;

-- name: SetActivePlaylist :one
INSERT INTO active_playlists (guild_id, playlist_id, activated_by)
VALUES ($1, $2, $3)
ON CONFLICT (guild_id) DO UPDATE SET 
    playlist_id = EXCLUDED.playlist_id,
    activated_at = NOW(),
    activated_by = EXCLUDED.activated_by
RETURNING *;

-- name: ClearActivePlaylist :exec
DELETE FROM active_playlists WHERE guild_id = $1;

-- name: GetGuildSettings :one
SELECT * FROM guild_settings WHERE guild_id = $1;

-- name: UpsertGuildSettings :one
INSERT INTO guild_settings (
    guild_id, 
    default_volume, 
    auto_disconnect_minutes, 
    announce_songs,
    restrict_to_dj_role,
    dj_role_id,
    default_repeat_mode
)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (guild_id) DO UPDATE SET
    default_volume = COALESCE(EXCLUDED.default_volume, guild_settings.default_volume),
    auto_disconnect_minutes = COALESCE(EXCLUDED.auto_disconnect_minutes, guild_settings.auto_disconnect_minutes),
    announce_songs = COALESCE(EXCLUDED.announce_songs, guild_settings.announce_songs),
    restrict_to_dj_role = COALESCE(EXCLUDED.restrict_to_dj_role, guild_settings.restrict_to_dj_role),
    dj_role_id = COALESCE(EXCLUDED.dj_role_id, guild_settings.dj_role_id),
    default_repeat_mode = COALESCE(EXCLUDED.default_repeat_mode, guild_settings.default_repeat_mode),
    updated_at = NOW()
RETURNING *;
