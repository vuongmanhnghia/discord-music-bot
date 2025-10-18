# Voice Connection Recovery System

## Vấn đề
Sau khi bot chạy được 1 thời gian, Discord WebSocket timeout xảy ra:
```
asyncio.exceptions.CancelledError
  → TimeoutError in poll_voice_ws (discord/voice_state.py:601)
  → No heartbeat received for 30+ seconds
```

Bot mất kết nối voice hoàn toàn và nhạc ngừng phát.

## Giải pháp đã triển khai

### 1. Event Handler cho Voice Errors (`music_bot.py`)

#### `on_error(event_method, *args, **kwargs)`
- Bắt tất cả lỗi trong event listeners
- Phát hiện voice connection errors (timeout, cancelled, websocket)
- Tự động gọi recovery nếu phát hiện vấn đề voice

```python
async def on_error(self, event_method: str, *args, **kwargs):
    """Handle errors in event listeners"""
    # Log exception details
    logger.error(f"Error in {event_method}: {exc_value}")
    
    # Check if it's a voice-related error
    if "voice" in event_method.lower():
        error_msg = str(exc_value).lower()
        if any(keyword in error_msg for keyword in ["timeout", "cancelled", "websocket", "connection"]):
            logger.warning(f"Voice connection issue detected: {exc_value}")
            await self._attempt_voice_recovery()
```

#### `_attempt_voice_recovery()`
- Kiểm tra tất cả voice clients
- Phát hiện client disconnected
- Gọi `audio_service.ensure_voice_connection()` để reconnect

```python
async def _attempt_voice_recovery(self):
    """Attempt to recover from voice connection issues"""
    for voice_client in self.voice_clients:
        if not voice_client.is_connected():
            guild_id = voice_client.guild.id
            await audio_service.ensure_voice_connection(guild_id)
```

### 2. Ensure Voice Connection (`audio_service.py`)

#### `ensure_voice_connection(guild_id)`
- Kiểm tra voice client có connected không
- Nếu disconnected:
  1. Cleanup old connection
  2. Tìm voice channel bot đang ở
  3. Reconnect với timeout
  4. Reinitialize audio player
  5. Resume playback nếu có bài hát đang phát

```python
async def ensure_voice_connection(self, guild_id: int) -> bool:
    voice_client = self._voice_clients.get(guild_id)
    
    # Already connected
    if voice_client and voice_client.is_connected():
        return True
    
    # Cleanup old connection
    if voice_client:
        await voice_client.disconnect()
    
    # Find channel and reconnect
    bot_member = guild.me
    if bot_member.voice and bot_member.voice.channel:
        channel = bot_member.voice.channel
        new_voice_client = await channel.connect()
        
        # Update connection
        self._voice_clients[guild_id] = new_voice_client
        await self._initialize_audio_player(guild_id, new_voice_client)
        
        # Resume playback
        if queue_manager.current_song:
            await self.play_next_song(guild_id)
        
        return True
```

### 3. Periodic Health Check (`music_bot.py`)

#### `_voice_health_check_loop()`
- Chạy background task kiểm tra mỗi 60 giây
- Phát hiện sớm voice clients disconnected
- Tự động recovery trước khi user nhận ra

```python
async def _voice_health_check_loop(self):
    """Periodically check voice connections and recover if needed"""
    await self.wait_until_ready()
    
    while not self.is_closed():
        try:
            await asyncio.sleep(60)  # Check every 60 seconds
            
            for voice_client in self.voice_clients:
                if not voice_client.is_connected():
                    guild_id = voice_client.guild.id
                    logger.warning(f"💔 Detected disconnected voice client")
                    await audio_service.ensure_voice_connection(guild_id)
                    
        except Exception as e:
            logger.error(f"Error in voice health check: {e}")
            await asyncio.sleep(60)  # Continue checking
```

## Luồng hoạt động

### Khi WebSocket Timeout xảy ra:

```
1. Discord WebSocket timeout (30s no heartbeat)
   ↓
2. discord.py raises TimeoutError/CancelledError
   ↓
3. on_error() catches exception
   ↓
4. Detects "voice" + "timeout" keywords
   ↓
5. Calls _attempt_voice_recovery()
   ↓
6. Checks voice_client.is_connected() → False
   ↓
7. Calls ensure_voice_connection()
   ↓
8. Cleans up old connection
   ↓
9. Finds voice channel bot is in
   ↓
10. Reconnects to channel
    ↓
11. Reinitializes audio player
    ↓
12. Resumes playback if song was playing
    ↓
13. ✅ Bot recovered, music continues
```

### Health Check (Preventive):

```
Every 60 seconds:
1. Loop through all voice_clients
   ↓
2. Check is_connected() status
   ↓
3. If disconnected:
   - Log warning
   - Call ensure_voice_connection()
   - Automatic recovery
```

## Lợi ích

1. **Tự động phục hồi**: Không cần admin can thiệp khi disconnect
2. **Phát hiện sớm**: Health check 60s phát hiện trước khi user biết
3. **Resume playback**: Tự động tiếp tục phát bài hát đang play
4. **Comprehensive logging**: Log chi tiết mọi bước recovery
5. **Error isolation**: Lỗi recovery không làm crash bot

## Log Messages

### Normal Operation:
```
💓 Voice health check started
```

### When Disconnect Detected:
```
💔 Detected disconnected voice client in guild 123456
🔄 Reconnecting to voice channel: General
✅ Successfully reconnected to General
🎵 Resuming playback after reconnection
```

### When Recovery Needed:
```
⚠️ Voice connection issue detected: TimeoutError
🔄 Attempting voice connection recovery...
✅ Voice recovery attempt completed
```

### Errors:
```
❌ Failed to reconnect voice in guild 123456: [error details]
Reconnection traceback: [full traceback]
```

## Testing

### Mô phỏng WebSocket timeout:
1. Start bot và play nhạc
2. Wait vài giờ hoặc force disconnect network
3. Bot sẽ tự động:
   - Detect disconnection
   - Reconnect to voice
   - Resume playback

### Health check test:
1. Manually disconnect bot (kick from channel)
2. Wait 60 seconds
3. Health check sẽ detect và auto-reconnect

## Cấu hình

### Timeout Settings (`config/service_constants.py`):
```python
VOICE_CONNECT_TIMEOUT = 10.0  # Reconnect timeout
VOICE_DISCONNECT_TIMEOUT = 5.0  # Cleanup timeout
```

### Health Check Interval (`music_bot.py`):
```python
await asyncio.sleep(60)  # Check every 60 seconds
```

Có thể điều chỉnh interval nếu cần check thường xuyên hơn (trade-off: CPU usage).

## Known Limitations

1. **Cannot reconnect nếu bot bị kick khỏi server**: Cần admin invite lại
2. **Short gap in playback**: 1-2 giây gap khi reconnecting (unavoidable)
3. **Requires bot still in voice channel**: Nếu bot bị kick khỏi channel, không thể tự reconnect

## Future Improvements

1. **Reconnect history tracking**: Track số lần reconnect để detect persistent issues
2. **Adaptive health check**: Tăng frequency nếu detect nhiều disconnects
3. **Metrics/alerting**: Alert admin nếu quá nhiều reconnects trong short period
4. **Preemptive reconnect**: Detect connection degradation trước timeout
