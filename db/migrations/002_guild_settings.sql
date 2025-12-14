-- +goose Up
-- +goose StatementBegin

-- Guild settings table: Store guild-specific configurations
CREATE TABLE guild_settings (
    guild_id VARCHAR(20) PRIMARY KEY REFERENCES guilds(id) ON DELETE CASCADE,
    default_volume INTEGER DEFAULT 30 CHECK (default_volume >= 0 AND default_volume <= 100),
    auto_disconnect_minutes INTEGER DEFAULT 5,
    announce_songs BOOLEAN DEFAULT true,
    restrict_to_dj_role BOOLEAN DEFAULT false,
    dj_role_id VARCHAR(20),
    default_repeat_mode VARCHAR(10) DEFAULT 'none' CHECK (default_repeat_mode IN ('none', 'track', 'queue')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Active playlists: Track which playlist is active per guild
CREATE TABLE active_playlists (
    guild_id VARCHAR(20) PRIMARY KEY REFERENCES guilds(id) ON DELETE CASCADE,
    playlist_id UUID REFERENCES playlists(id) ON DELETE SET NULL,
    activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_by VARCHAR(20)
);

-- Favorite songs: Allow users to save favorite songs
CREATE TABLE user_favorites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(20) NOT NULL,  -- Discord user ID
    original_input TEXT NOT NULL,
    source_type VARCHAR(20) NOT NULL DEFAULT 'youtube',
    title VARCHAR(500),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT unique_favorite_per_user UNIQUE (user_id, original_input)
);

-- Indexes
CREATE INDEX idx_user_favorites_user_id ON user_favorites(user_id);
CREATE INDEX idx_active_playlists_playlist_id ON active_playlists(playlist_id);

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin

DROP TABLE IF EXISTS user_favorites;
DROP TABLE IF EXISTS active_playlists;
DROP TABLE IF EXISTS guild_settings;

-- +goose StatementEnd
