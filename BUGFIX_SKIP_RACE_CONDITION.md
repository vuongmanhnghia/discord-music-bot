# 🐛 Bug Fix: Skip Command Race Condition

## Problem Description

When using `/skip` command, the bot encountered "Already playing audio" error and failed to skip properly.

### Error Log
```
2025-11-01 08:26:03 | ERROR | ❌ Error playing Viral talking Cat Meme: Already playing audio.
2025-11-01 08:26:03 | WARNING | ⚠️ Failed to play next song, trying again...
```

## Root Cause Analysis

### The Race Condition

When `/skip` was executed, a **race condition** occurred:

1. **`skip_current_song()`** calls `audio_player.stop()`
2. **FFmpeg callback** `_after_playback()` is triggered
3. **Callback** automatically calls `_play_next_song()` → `play_song()`
4. **Meanwhile**, `skip_current_song()` also calls `await self.play_next_song()`
5. **Result**: Two calls to `play_song()` happen simultaneously

### Why It Failed

```python
# First call from callback
voice_client.play(audio_source)  # Starts playing

# Second call from skip_current_song
voice_client.play(audio_source)  # ERROR: Already playing audio!
```

The FFmpeg process doesn't terminate instantly, so the voice client thinks it's still playing when the second `play()` is called.

## Solution

### Approach: Controlled Auto-Play

Added `auto_play_next` parameter to `stop()` method to control whether the callback should trigger auto-play.

### Changes Made

#### 1. Enhanced `AudioPlayer.stop()` Method

**File**: `bot/services/audio/audio_player.py`

```python
def stop(self, auto_play_next: bool = True) -> bool:
    """
    Stop playback

    Args:
        auto_play_next: If True, triggers auto-play next song via callback.
                      If False, prevents auto-play (used for manual skip/stop).
    """
    if self.voice_client.is_playing() or self.voice_client.is_paused():
        # Prevent auto-play if requested (for manual operations)
        if not auto_play_next:
            self._is_disconnected = True

        self.voice_client.stop()
        self.current_song = None
        self.is_playing = False
        self.is_paused = False

        # Re-enable auto-play after stop completes
        if not auto_play_next:
            asyncio.create_task(self._reset_auto_play_flag())

        return True
    return False

async def _reset_auto_play_flag(self):
    """Reset auto-play flag after stop completes"""
    await asyncio.sleep(0.5)
    self._is_disconnected = False
```

#### 2. Updated `skip_current_song()`

**File**: `bot/services/audio/audio_service.py`

```python
async def skip_current_song(self, guild_id: int) -> bool:
    """Skip current song"""
    try:
        audio_player = self._audio_players.get(guild_id)
        if not audio_player:
            return False

        if not audio_player.is_playing:
            return False

        # Stop with auto_play_next=False to prevent callback from playing next
        audio_player.stop(auto_play_next=False)
        logger.info(f"⏭️ Skipped song in guild {guild_id}")

        # Wait for FFmpeg to fully terminate
        await asyncio.sleep(FFMPEG_CLEANUP_DELAY)

        # Manually play next song (callback won't do it)
        await self.play_next_song(guild_id)
        return True
    except Exception as e:
        logger.error(f"❌ Error skipping song: {e}")
        return False
```

#### 3. Updated `stop_playback()`

**File**: `bot/services/playback_service.py`

```python
async def stop_playback(self, guild_id: int) -> tuple[bool, str]:
    """Stop playback and clear tracklist"""
    try:
        # Stop audio with auto_play_next=False to prevent callback
        audio_player = self.audio_service.get_audio_player(guild_id)
        if audio_player:
            audio_player.stop(auto_play_next=False)

        # Clear tracklist
        tracklist = self.audio_service.get_tracklist(guild_id)
        if tracklist:
            await tracklist.clear()

        # ... rest of the code
```

## How It Works Now

### Skip Flow (Fixed)

```
User: /skip
    ↓
skip_current_song()
    ↓
audio_player.stop(auto_play_next=False)  ← Prevents callback auto-play
    ↓
_is_disconnected = True  ← Blocks callback
    ↓
voice_client.stop()  ← Triggers callback
    ↓
_after_playback() checks _is_disconnected
    ↓
Callback SKIPS auto-play (because _is_disconnected=True)
    ↓
await sleep(FFMPEG_CLEANUP_DELAY)  ← Wait for cleanup
    ↓
await self.play_next_song(guild_id)  ← Manual play next
    ↓
_reset_auto_play_flag()  ← Re-enable for future
    ↓
✅ Success!
```

### Normal Playback (Unchanged)

```
Song finishes naturally
    ↓
_after_playback() called
    ↓
_is_disconnected == False  ← Auto-play enabled
    ↓
_play_next_song() called by callback
    ↓
✅ Auto-play next song
```

## Benefits

1. ✅ **Prevents race condition** - Only one play call happens
2. ✅ **Maintains auto-play** - Normal playback still auto-advances
3. ✅ **Clean separation** - Manual operations vs auto-play clearly separated
4. ✅ **Backward compatible** - Default behavior unchanged (`auto_play_next=True`)
5. ✅ **Proper cleanup** - Waits for FFmpeg termination

## Testing

### Test Case 1: Skip Command
```
✅ Play song
✅ Use /skip
✅ Next song starts immediately
✅ No "Already playing audio" error
```

### Test Case 2: Natural Playback
```
✅ Play multiple songs
✅ Let first song finish
✅ Next song auto-plays
✅ Queue advances normally
```

### Test Case 3: Stop Command
```
✅ Play song
✅ Use /stop
✅ Playback stops
✅ Queue cleared
✅ No auto-play triggered
```

## Related Files Modified

- `bot/services/audio/audio_player.py` - Added `auto_play_next` parameter
- `bot/services/audio/audio_service.py` - Updated `skip_current_song()`
- `bot/services/playback_service.py` - Updated `stop_playback()`

## Additional Notes

### Why Not Just Remove Callback Auto-Play?

The callback auto-play is essential for:
- Seamless queue progression
- Repeat modes
- 24/7 operation
- Stream URL refresh retry

Removing it would break core functionality.

### Why The Delay?

The `await asyncio.sleep(FFMPEG_CLEANUP_DELAY)` is necessary because:
1. FFmpeg doesn't terminate instantly
2. Voice client needs time to reset
3. Prevents "Already playing" errors
4. Ensures clean state transition

## Additional Bug Found & Fixed

### Bug #2: Skip Playing Same Song

**Problem**: After fixing the race condition, skip was replaying the same song instead of advancing to the next one.

**Root Cause**: In `play_next_song()`, the code was using:
```python
# BUG: Gets current song instead of advancing
next_song = self._tracklists[guild_id].current_song  # ❌ WRONG
```

**Fix**: Changed to properly advance the tracklist:
```python
# FIXED: Calls next_song() to advance position
next_song = await self._tracklists[guild_id].next_song()  # ✅ CORRECT
```

**Impact**: Skip now properly advances to the next song in the queue.

---

## Status

✅ **FIXED** - Skip command now works reliably without race conditions.
✅ **FIXED** - Skip properly advances to next song.

---

*Bug #1 (Race condition) identified and fixed: 2025-11-01*
*Bug #2 (Wrong song) identified and fixed: 2025-11-01*
*Impact: HIGH - Core playback functionality*
*Severity: CRITICAL - User-facing command failure*
