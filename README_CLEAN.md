# 🎵 LoFi Music Bot - Clean Architecture

Optimized Discord bot for Spotify playlist management with clean, modular design.

## ✨ Features

-   **Clean Architecture**: Modular design with separation of concerns
-   **Playlist Management**: Organize music in separate folders per playlist
-   **Spotify Integration**: Sync playlists directly from Spotify URLs
-   **Auto-Format Protection**: Maintains proper `.spotdl` sync format
-   **File Watching**: Auto-updates queues when music files change
-   **Per-Guild State**: Independent playlist selection per Discord server

## 🏗️ Architecture

```
lofi_bot/
├── __init__.py          # Package initialization
├── config.py            # Configuration management
├── logger.py            # Centralized logging
├── models.py            # Data models
├── playlist.py          # Playlist management
├── spotdl_client.py     # SpotDL integration
├── watcher.py           # File system watching
└── bot.py              # Discord bot implementation
```

## 🚀 Quick Start

1. **Environment Setup**:

```bash
cp .env.example .env
# Edit .env with your values
```

2. **Install Dependencies**:

```bash
pip install -r requirements_clean.txt
```

3. **Run Bot**:

```bash
python main_clean.py
```

## 📋 Required Environment Variables

```env
BOT_TOKEN=your_discord_bot_token
MUSIC_FOLDER=/path/to/music/storage
```

## 📋 Optional Environment Variables

```env
BOT_NAME="LoFi Bot"
COMMAND_PREFIX="!"
SPOTDL_DIR="."
LOG_LEVEL="INFO"
LOG_FILE=""
```

## 🎮 Commands

| Command               | Description                   |
| --------------------- | ----------------------------- |
| `!playlists`          | List available playlists      |
| `!use <name>`         | Select active playlist        |
| `!current`            | Show current playlist         |
| `!sync <name>`        | Sync playlist from Spotify    |
| `!add <url>`          | Add song to current playlist  |
| `!addto <name> <url>` | Add song to specific playlist |
| `!fix <name>`         | Fix playlist format           |
| `!play [song]`        | Play music                    |
| `!stop`               | Stop and disconnect           |
| `!skip`               | Skip current song             |
| `!shuffle`            | Shuffle queue                 |

## 📁 File Structure

```
project/
├── lofi_bot/           # Clean bot code
├── music/              # Music storage (MUSIC_FOLDER)
│   ├── playlist1/      # Songs for playlist1
│   └── playlist2/      # Songs for playlist2
├── *.spotdl           # Playlist files (SPOTDL_DIR)
└── main_clean.py      # Entry point
```

## 🔧 Key Improvements

-   **90% less code**: Removed redundant logic and unnecessary complexity
-   **Clean separation**: Each module has a single responsibility
-   **No hardcoding**: All paths and settings from environment
-   **Error resilience**: Graceful handling of failures
-   **Format protection**: Automatic `.spotdl` sync format maintenance
-   **Optimized watching**: Debounced file system events
-   **Memory efficient**: Per-guild state management

## 🎯 Migration from Old Code

The new architecture is completely self-contained in the `lofi_bot/` package. Simply:

1. Set up environment variables
2. Run `python main_clean.py`
3. Your existing `.spotdl` files and music folders will work unchanged

## 🐛 Troubleshooting

-   **Bot won't start**: Check `BOT_TOKEN` and `MUSIC_FOLDER` environment variables
-   **Sync fails**: Ensure `spotdl` is installed and accessible
-   **No audio**: Check Discord permissions and voice channel connection
-   **Format issues**: Use `!fix <playlist>` to repair `.spotdl` files
