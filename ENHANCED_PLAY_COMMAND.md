# Enhanced /play Command - Auto-Playback Feature

## Overview

The `/play` command has been enhanced to support auto-playback from active playlists, making the playlist workflow much more user-friendly.

## Key Enhancement

### Before Enhancement

```
/use my_playlist    → Load playlist to queue
/play <song URL>    → User must manually provide URLs
```

### After Enhancement

```
/use my_playlist    → Load playlist as active + Load to queue
/play               → Auto-start playing from active playlist
/play <query>       → Normal search/URL behavior (unchanged)
```

## How It Works

### 1. Two-Mode Operation

-   **Mode 1**: `/play <query>` - Normal URL/search behavior (unchanged)
-   **Mode 2**: `/play` (no query) - Auto-play from active playlist (NEW)

### 2. Active Playlist Tracking

-   Each Discord guild can have one active playlist
-   Set by `/use <playlist>` command
-   Stored in `self.active_playlists: dict[int, str]`

### 3. Auto-Playback Logic

```python
if query:
    # Mode 1: Normal play behavior
    await playback_service.play_request(query, ...)
else:
    # Mode 2: Enhanced playlist behavior
    active_playlist = self.active_playlists.get(guild_id)
    if active_playlist:
        # Load playlist to queue
        await self.playlist_service.load_playlist_to_queue(...)

        # Auto-start if not currently playing
        if not audio_player.is_playing:
            await audio_service.play_next_song(guild_id)
```

## Technical Implementation

### Code Changes in `music_bot.py`

1. **Active Playlist Tracking**:

    ```python
    # Track current active playlist for each guild
    self.active_playlists: dict[int, str] = {}
    ```

2. **Enhanced /play Command**:

    ```python
    @self.tree.command(name="play", description="Phát nhạc từ URL/tìm kiếm hoặc từ playlist hiện tại")
    @app_commands.describe(query="URL hoặc từ khóa tìm kiếm (để trống để phát từ playlist hiện tại)")
    async def play_music(interaction: discord.Interaction, query: Optional[str] = None):
    ```

3. **Auto-Playback Logic**:
    ```python
    # Auto-start playing if not currently playing
    audio_player = audio_service.get_audio_player(guild_id)
    if audio_player and not audio_player.is_playing:
        started = await audio_service.play_next_song(guild_id)
        if started:
            embed.add_field(name="🎵 Trạng thái", value="Đã bắt đầu phát nhạc!", inline=False)
    ```

## User Experience Improvements

### Workflow Comparison

#### Old Workflow

```
1. /use my_playlist           → Load to queue
2. /play <copy-paste-URL>     → Find and copy URLs manually
3. Repeat step 2 for each song
```

#### New Workflow

```
1. /use my_playlist           → Load to queue + Set as active
2. /play                      → Auto-start from playlist!
3. /play                      → Continue with next songs
```

### User Benefits

-   **Reduced Friction**: No need to manually copy URLs from playlist
-   **Intuitive Behavior**: `/play` works logically with active playlist
-   **Backward Compatible**: All existing commands work unchanged
-   **Smart Detection**: Automatically chooses correct mode based on parameters

## Error Handling

### No Active Playlist

```
❌ Chưa có playlist nào được chọn!
Sử dụng `/use <playlist>` trước hoặc cung cấp query để tìm kiếm.
```

### Songs Not Ready

```
⚠️ Đã thêm vào queue, nhưng chưa có bài nào sẵn sàng phát
```

### Auto-Start Success

```
✅ Đã nạp playlist
📋 my_playlist
Added 5 songs from playlist 'my_playlist' to queue
🎵 Trạng thái: Đã bắt đầu phát nhạc!
```

## Command Reference

### Enhanced Commands

-   `/play` - Auto-play from active playlist
-   `/play <query>` - Search/URL play (unchanged)
-   `/use <playlist>` - Set active playlist + load to queue
-   `/add <song>` - Add to active playlist
-   `/addto <playlist> <song>` - Add to specific playlist

### Workflow Examples

#### Basic Playlist Usage

```
/create rock_songs
/addto rock_songs https://youtube.com/watch?v=abc123
/addto rock_songs https://youtube.com/watch?v=def456
/use rock_songs        # Load + set as active
/play                  # Auto-start playing!
```

#### Mixed Usage

```
/use my_favorites      # Set active playlist
/play                  # Play from favorites
/play bohemian rhapsody # Search for specific song
/play                  # Resume from favorites
```

## Technical Notes

### State Management

-   Active playlists are per-guild (server-specific)
-   Cleared when bot restarts (memory-only storage)
-   Could be persisted to disk if needed

### Queue Integration

-   Playlist songs are loaded as regular Song objects
-   Queue manager handles playback order
-   Works with existing repeat/shuffle features

### Performance

-   Playlists loaded on-demand
-   Songs processed asynchronously
-   No impact on existing /play performance

## Future Enhancements

### Potential Improvements

1. **Persistent Active Playlist**: Remember active playlist across restarts
2. **Playlist Position**: Resume from specific position in playlist
3. **Auto-Advance**: Automatically load more songs when queue runs low
4. **Smart Shuffling**: Intelligent playlist randomization

### Advanced Features

1. **Playlist Modes**: Sequential, shuffle, repeat modes per playlist
2. **Queue Mix**: Blend playlist with manual additions
3. **Playlist History**: Track recently used playlists
4. **Cross-Guild Sync**: Share playlists across servers
