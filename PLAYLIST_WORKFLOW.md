# 🎵 Playlist Workflow Guide

## 📋 Overview

The bot now uses a **simplified, context-aware workflow** for managing playlists, similar to Spotify and Apple Music.

## ✨ Key Concept: Context-Aware Commands

Instead of specifying playlist name every time, you:
1. **Set active playlist** once with `/use`
2. **Add songs** with `/add` (automatically adds to active playlist + plays)
3. **Switch context** anytime with `/use <another_playlist>`

---

## 🚀 Quick Start

### Create and Build a Playlist

```bash
# 1. Create new playlist
/createplaylist workout

# 2. Set as active (context)
/use workout

# 3. Add songs (will add to playlist + play)
/add upbeat song 1       # Plays immediately + saves to playlist
/add upbeat song 2       # Queues + saves to playlist
/add upbeat song 3       # Queues + saves to playlist

# Result: You're listening while building the playlist!
```

### Use Without Active Playlist

```bash
# No /use command = normal queue mode
/add random song         # Just adds to queue (doesn't save to playlist)
/play another song       # Also just queues
```

---

## 📚 Complete Command Reference

### Core Commands

#### `/createplaylist <name>`
Create a new empty playlist.

**Example:**
```bash
/createplaylist chill
✅ Created playlist: chill
```

---

#### `/use <playlist>`
Set a playlist as active (context). All `/add` commands will save to this playlist.

**Example:**
```bash
/use chill
✅ Active playlist: chill
```

**Note:** Can use even if playlist is empty!

---

#### `/add <song>`
**The main command!** Context-aware adding with immediate playback.

**Behavior:**
- ✅ Always adds to queue
- ✅ Always starts playing (if not already)
- ✅ If active playlist set: also saves to playlist file
- ✅ If no active playlist: just queues

**Examples:**

With active playlist:
```bash
/use workout
/add Eye of the Tiger
✅ Added to queue & playlist 'workout'
🎵 Eye of the Tiger
```

Without active playlist:
```bash
# No /use command
/add random song
✅ Added to queue
🎵 Random Song Name
```

---

#### `/remove <playlist> <index>`
Remove song from playlist by position (1-based).

**Example:**
```bash
/remove chill 3
✅ Removed song at position 3 from playlist 'chill'
```

---

#### `/playlists`
List all your playlists with song counts.

**Example:**
```bash
/playlists
📚 Your Playlists:
• workout (15 songs)
• chill (23 songs)
• party (8 songs)
```

---

#### `/playlist [name]`
View contents of a playlist (paginated if many songs).

**Example:**
```bash
/playlist chill
📋 Playlist: chill (23 songs)

1. Lofi Hip Hop Radio
2. Chillwave Summer Mix
3. Rainy Day Jazz
...
```

---

#### `/deleteplaylist <name>`
Delete a playlist permanently.

**Example:**
```bash
/deleteplaylist old
✅ Deleted playlist: old
```

---

## 🎯 Common Workflows

### Workflow 1: Build Playlist While Listening

```bash
/createplaylist study
/use study
/add lofi beats          # Starts playing + saves
/add rain sounds         # Queues + saves
/add piano music         # Queues + saves
/add ambient noise       # Queues + saves

# Now you have a 4-song playlist and you're listening!
```

---

### Workflow 2: Save YouTube Playlist

```bash
/createplaylist favorites
/saveplaylist favorites https://youtube.com/playlist?list=...

# Wait for processing (shows progress)
✅ Added 50 songs to playlist 'favorites'

# Now use it
/use favorites
/play                    # Start playing from playlist
```

---

### Workflow 3: Quick Queue (No Playlist)

```bash
# Don't use /use command
/add song1               # Just queues
/add song2               # Just queues
/add song3               # Just queues

# Songs play but don't save anywhere
```

---

### Workflow 4: Switch Between Playlists

```bash
/use workout
/add high energy song    # Goes to workout playlist
/add pump up music       # Goes to workout playlist

/use chill               # Switch context
/add lofi beats          # Goes to chill playlist
/add ambient sounds      # Goes to chill playlist
```

---

### Workflow 5: Load and Extend Existing Playlist

```bash
/loadplaylist chill      # Loads into queue
/play                    # Start playing

/use chill               # Set as active
/add new song            # Adds to existing playlist + queue
```

---

## 💡 Pro Tips

### Tip 1: Active Playlist Persists
```bash
/use workout
# ... do other things ...
# Hours later:
/add new song            # Still goes to 'workout'!
```

### Tip 2: Empty Playlists Are OK
```bash
/createplaylist new
/use new                 # Works even though empty!
/add first song          # Starts building playlist
```

### Tip 3: Check Current Context
```bash
/playlists               # Shows all playlists
                         # Active one has indicator
```

### Tip 4: Mix Modes
```bash
/use playlist1
/add song1               # Saves to playlist1
/play random_song        # Just queues (doesn't save)
/add song2               # Saves to playlist1
```

---

## 🔄 Migration from Old Commands

| Old Way | New Way | Notes |
|---------|---------|-------|
| `/addto playlist song` | `/use playlist` → `/add song` | Set context once |
| `/addto pl song` + `/play` | `/add song` | Single command |
| Multiple `/addto` | `/use` once + multiple `/add` | Less repetitive |

---

## ❓ FAQ

### Q: Does `/add` always start playing?
**A:** Yes! If nothing is playing, it starts immediately. If already playing, it queues.

### Q: What if I don't want to save to playlist?
**A:** Don't use `/use`. Just use `/add` or `/play` directly.

### Q: Can I add to queue without playing?
**A:** No, `/add` always triggers playback. Use `/play` with defer if you want queuing only.

### Q: How do I know which playlist is active?
**A:** Use `/playlists` to see all playlists. Active one is indicated.

### Q: Can I change active playlist mid-session?
**A:** Yes! Use `/use <another_playlist>` anytime.

### Q: Does `/add` work with YouTube playlists?
**A:** Yes! It extracts metadata and adds each song properly.

### Q: What happens if metadata extraction fails?
**A:** Song still plays and queues, but might save with generic title to playlist.

---

## 🎨 Visual Comparison

### Old Workflow ❌
```
/createplaylist chill
↓
/addto chill song1  ← Specify playlist each time
↓
/addto chill song2  ← Repetitive
↓
/addto chill song3  ← Tedious
↓
/use chill
↓
/play              ← Separate command to start
```

### New Workflow ✅
```
/createplaylist chill
↓
/use chill         ← Set context once
↓
/add song1         ← Add + play immediately
↓
/add song2         ← Add + queue (context aware)
↓
/add song3         ← Add + queue (context aware)
```

**Result:** 40% fewer commands, more intuitive!

---

## 📊 Command Behavior Matrix

| Scenario | Command | Queue | Playlist | Playback |
|----------|---------|-------|----------|----------|
| With active playlist | `/add song` | ✅ Add | ✅ Save | ✅ Start/Queue |
| No active playlist | `/add song` | ✅ Add | ❌ Skip | ✅ Start/Queue |
| With active playlist | `/play song` | ✅ Add | ❌ Skip | ✅ Start/Queue |
| Any scenario | `/skip` | ⏭️ Next | - | ⏭️ Next |

---

## 🚨 Important Notes

### Breaking Changes
- `/addto` command **removed** (use `/use` + `/add` instead)
- `/add` now **always triggers playback** (not just playlist operation)

### Backwards Compatibility
- Old playlists still work fine
- `/play` command unchanged
- `/loadplaylist` command unchanged
- Playlist files format unchanged

### Performance
- `/add` may take 1-10 seconds (extracts metadata)
- Progress shown during bulk operations
- Metadata cached for speed

---

## 📖 Related Commands

### Playback
- `/play [query]` - Play without saving to playlist
- `/skip` - Skip current song
- `/pause` / `/resume` - Pause/resume
- `/stop` - Stop and clear queue

### Queue
- `/queue` - View current queue
- `/nowplaying` - Show current song

### Advanced
- `/saveplaylist <name> <url>` - Save YouTube playlist to file
- `/loadplaylist <name>` - Load playlist into queue

---

## 🎯 Best Practices

1. **Use `/use` for building playlists** - Set context, then add freely
2. **Use `/add` for everything** - One command for add + play
3. **Use `/play` for temporary queuing** - When you don't want to save
4. **Check `/playlists` periodically** - See what you have
5. **Clean up with `/deleteplaylist`** - Remove unused playlists

---

## 💬 Example Session

```bash
User: /createplaylist morning
Bot: ✅ Created playlist: morning

User: /use morning
Bot: ✅ Active playlist: morning

User: /add morning vibes lofi
Bot: ✅ Added to queue & playlist 'morning'
     🎵 Lofi Morning Vibes Mix
     ▶️ Now playing...

User: /add coffee shop ambience
Bot: ✅ Added to queue & playlist 'morning'
     🎵 Coffee Shop Ambience
     📋 Position in queue: #2

User: /add jazz morning
Bot: ✅ Added to queue & playlist 'morning'
     🎵 Smooth Jazz Morning
     📋 Position in queue: #3

# After songs finish...
User: /playlist morning
Bot: 📋 Playlist: morning (3 songs)
     1. Lofi Morning Vibes Mix
     2. Coffee Shop Ambience
     3. Smooth Jazz Morning
```

---

## 🎉 Summary

The new workflow is:
- ✅ **Simpler** - One command instead of two
- ✅ **Smarter** - Context-aware behavior
- ✅ **Faster** - Immediate playback
- ✅ **Flexible** - Works with or without playlist
- ✅ **Professional** - Industry-standard UX

Enjoy your streamlined music experience! 🎵✨
