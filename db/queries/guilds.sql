-- name: GetGuild :one
SELECT * FROM guilds WHERE id = $1;

-- name: UpsertGuild :one
INSERT INTO guilds (id, name, joined_at)
VALUES ($1, $2, NOW())
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
RETURNING *;

-- name: DeleteGuild :exec
DELETE FROM guilds WHERE id = $1;

-- name: ListGuilds :many
SELECT * FROM guilds ORDER BY joined_at DESC;
