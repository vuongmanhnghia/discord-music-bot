# 🎵 Playlist Commands - Quick Reference

## 🚀 Most Used Commands

```bash
# 1. Create playlist
/createplaylist <name>

# 2. Set as active
/use <playlist>

# 3. Add songs (plays + saves)
/add <song>
```

## 📋 Full Command List

| Command | Description | Example |
|---------|-------------|---------|
| `/createplaylist <name>` | Create new playlist | `/createplaylist workout` |
| `/use <playlist>` | Set active playlist | `/use workout` |
| `/add <song>` | Add to queue + playlist + play | `/add lofi beats` |
| `/remove <playlist> <idx>` | Remove song from playlist | `/remove workout 5` |
| `/playlists` | List all playlists | `/playlists` |
| `/playlist [name]` | View playlist contents | `/playlist workout` |
| `/deleteplaylist <name>` | Delete playlist | `/deleteplaylist old` |
| `/saveplaylist <name> <url>` | Save YouTube playlist | `/saveplaylist chill https://...` |
| `/loadplaylist <name>` | Load playlist to queue | `/loadplaylist workout` |

## 🎯 Quick Workflows

### Build Playlist While Listening
```bash
/createplaylist study
/use study
/add song1    # Plays
/add song2    # Queues
/add song3    # Queues
```

### Just Queue (No Playlist)
```bash
# No /use command
/add song1    # Just queues
/add song2    # Just queues
```

### Switch Context
```bash
/use playlist1
/add song     # Goes to playlist1

/use playlist2
/add song     # Goes to playlist2
```

## 💡 Key Points

- ✅ `/add` always plays + queues
- ✅ `/add` saves to active playlist (if set)
- ✅ `/use` sets context once
- ✅ Empty playlists are OK
- ❌ `/addto` removed (use `/use` + `/add`)

## 📖 Full Guide

See `PLAYLIST_WORKFLOW.md` for complete documentation.
