# 🔧 Troubleshooting Guide

## ✅ **Bot Fixed Issues:**

### **Commands Not Responding** - ✅ FIXED

-   **Problem**: Bot wasn't registering commands properly
-   **Solution**: Fixed command registration in `lofi_bot/bot.py`
-   **Status**: ✅ All 12 commands now work with prefix `l!`

### **Infinite Music Error Loop** - ✅ FIXED

-   **Problem**: Bot got stuck trying to play the same failed songs repeatedly
-   **Solution**: Added intelligent retry logic with failure tracking
-   **Status**: ✅ Bot now tries max 3 different songs before giving up

### **FFmpeg Options Error** - ✅ FIXED

-   **Problem**: FFmpeg `reconnect` options not supported, file path issues
-   **Solution**: Simplified FFmpeg options and normalized file paths
-   **Status**: ✅ Bot now uses compatible FFmpeg options with absolute paths

## 🎵 **Music Playback Troubleshooting:**

### **If Bot Says "Unable to play any songs":**

1. **Check Voice Channel Connection:**

    ```
    - Join a voice channel first
    - Make sure bot has "Connect" and "Speak" permissions
    - Try l!stop and l!play again
    ```

2. **Check Music Files:**

    ```bash
    ls -la music/main_playlist/
    # Files should be .mp3 format and readable
    ```

3. **Check Bot Permissions:**

    - ✅ Read Messages
    - ✅ Send Messages
    - ✅ Connect (to voice)
    - ✅ Speak (in voice)
    - ✅ Use Voice Activity

4. **Check FFmpeg:**
    ```bash
    which ffmpeg  # Should show path
    ```

### **Common Solutions:**

1. **Reset Bot State:**

    ```
    l!stop
    l!use main_playlist
    l!play
    ```

2. **Check Playlist:**

    ```
    l!playlists
    l!current
    ```

3. **Test Single Song:**
    ```
    l!play Synchronize
    ```

## 📋 **Quick Commands Reference:**

| Command               | Purpose                    |
| --------------------- | -------------------------- |
| `l!help`              | Show all commands          |
| `l!playlists`         | List available playlists   |
| `l!use main_playlist` | Select playlist            |
| `l!current`           | Show current playlist      |
| `l!play`              | Play all songs in playlist |
| `l!play <song>`       | Play specific song         |
| `l!stop`              | Stop and disconnect        |
| `l!skip`              | Skip current song          |

## 🚀 **Testing:**

Run the test script to verify everything works:

```bash
python test_bot.py
```

## 🔍 **Debug Mode:**

To see detailed logs, set in `.env`:

```
LOG_LEVEL=DEBUG
```

Then restart the bot and check logs for detailed error messages.

## ✅ **What's Fixed:**

-   ✅ Command registration working
-   ✅ Bot responds to `l!` commands
-   ✅ Infinite loop prevention
-   ✅ Better error messages
-   ✅ Voice connection error handling
-   ✅ File existence checking
-   ✅ Retry logic for failed songs
-   ✅ FFmpeg compatibility issues fixed
-   ✅ File path normalization

Your bot should now work properly! 🎉
