-- name: AddToPlayHistory :one
INSERT INTO play_history (
    guild_id, 
    original_input, 
    source_type, 
    title, 
    played_by,
    duration_seconds,
    completed
)
VALUES ($1, $2, $3, $4, $5, $6, $7)
RETURNING *;

-- name: GetRecentPlayHistory :many
SELECT * FROM play_history 
WHERE guild_id = $1 
ORDER BY played_at DESC 
LIMIT $2;

-- name: GetMostPlayedSongs :many
SELECT 
    original_input,
    title,
    source_type,
    COUNT(*) AS play_count,
    MAX(played_at) AS last_played
FROM play_history 
WHERE guild_id = $1
GROUP BY original_input, title, source_type
ORDER BY play_count DESC
LIMIT $2;

-- name: MarkPlayCompleted :exec
UPDATE play_history SET completed = true WHERE id = $1;

-- name: ClearPlayHistory :exec
DELETE FROM play_history WHERE guild_id = $1;

-- name: GetUserFavorites :many
SELECT * FROM user_favorites 
WHERE user_id = $1 
ORDER BY added_at DESC;

-- name: AddUserFavorite :one
INSERT INTO user_favorites (user_id, original_input, source_type, title)
VALUES ($1, $2, $3, $4)
ON CONFLICT (user_id, original_input) DO NOTHING
RETURNING *;

-- name: RemoveUserFavorite :exec
DELETE FROM user_favorites WHERE user_id = $1 AND original_input = $2;

-- name: IsFavorite :one
SELECT EXISTS(
    SELECT 1 FROM user_favorites WHERE user_id = $1 AND original_input = $2
);
