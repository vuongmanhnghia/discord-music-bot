-- +goose Up
-- +goose StatementBegin

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Guilds table: Track Discord guilds
CREATE TABLE guilds (
    id VARCHAR(20) PRIMARY KEY,  -- Discord snowflake ID
    name VARCHAR(100),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    settings JSONB DEFAULT '{}'::jsonb
);

-- Playlists table: Store playlist metadata
CREATE TABLE playlists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    guild_id VARCHAR(20) REFERENCES guilds(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT true,
    created_by VARCHAR(20),  -- Discord user ID
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Unique playlist name per guild (NULL guild_id means global)
    CONSTRAINT unique_playlist_name_per_guild UNIQUE (guild_id, name)
);

-- Playlist entries table: Store individual songs
CREATE TABLE playlist_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    playlist_id UUID NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    original_input TEXT NOT NULL,
    source_type VARCHAR(20) NOT NULL DEFAULT 'youtube',
    title VARCHAR(500),
    duration_seconds INTEGER,
    thumbnail_url TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    added_by VARCHAR(20),  -- Discord user ID
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Prevent duplicate songs in same playlist
    CONSTRAINT unique_entry_per_playlist UNIQUE (playlist_id, original_input)
);

-- Play history table: Track what songs have been played (for analytics)
CREATE TABLE play_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    guild_id VARCHAR(20) REFERENCES guilds(id) ON DELETE CASCADE,
    original_input TEXT NOT NULL,
    source_type VARCHAR(20) NOT NULL DEFAULT 'youtube',
    title VARCHAR(500),
    played_by VARCHAR(20),  -- Discord user ID
    played_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    duration_seconds INTEGER,
    completed BOOLEAN DEFAULT false
);

-- Indexes for performance
CREATE INDEX idx_playlists_guild_id ON playlists(guild_id);
CREATE INDEX idx_playlists_name ON playlists(name);
CREATE INDEX idx_playlist_entries_playlist_id ON playlist_entries(playlist_id);
CREATE INDEX idx_playlist_entries_position ON playlist_entries(playlist_id, position);
CREATE INDEX idx_play_history_guild_id ON play_history(guild_id);
CREATE INDEX idx_play_history_played_at ON play_history(played_at DESC);

-- Updated at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to playlists table
CREATE TRIGGER update_playlists_updated_at
    BEFORE UPDATE ON playlists
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin

DROP TRIGGER IF EXISTS update_playlists_updated_at ON playlists;
DROP FUNCTION IF EXISTS update_updated_at_column();
DROP TABLE IF EXISTS play_history;
DROP TABLE IF EXISTS playlist_entries;
DROP TABLE IF EXISTS playlists;
DROP TABLE IF EXISTS guilds;
DROP EXTENSION IF EXISTS "uuid-ossp";

-- +goose StatementEnd
