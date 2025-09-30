# 🛠️ Auto-Recovery System Documentation

## Tổng quan

Hệ thống Auto-Recovery được thiết kế để tự động phát hiện và xử lý các lỗi YouTube 403 Forbidden, giúp bot hoạt động liên tục mà không cần can thiệp thủ công.

## Tính năng chính

### 🚨 Tự động phát hiện lỗi

-   **403 Forbidden errors**: "Server returned 403 Forbidden", "HTTP Error 403"
-   **Rate limit errors**: "Rate limit exceeded", "Too many requests"
-   **Extraction errors**: "Unable to extract", "Error opening input file"

### 🔄 Tự động recovery

-   **Clear yt-dlp cache**: Xóa cache cũ gây conflict
-   **Clear bot cache**: Xóa cache songs và metadata
-   **Update yt-dlp**: Cập nhật phiên bản mới nhất
-   **Cooldown system**: Ngăn recovery quá thường xuyên (5 phút)

### ⏰ Scheduled maintenance

-   **Định kỳ 6 tiếng**: Tự động bảo trì hệ thống
-   **Cleanup old cache**: Xóa cache files cũ
-   **Update yt-dlp**: Cập nhật weekly nếu cần

## Commands

### `/recovery`

Kiểm tra trạng thái auto-recovery system:

-   Trạng thái enable/disable
-   Số lần recovery đã thực hiện
-   Thời gian recovery cuối cùng
-   Thời gian cooldown còn lại
-   Thông tin các tính năng

## Cấu hình

### Constants (config/constants.py)

```python
# Auto-recovery settings
AUTO_RECOVERY_COOLDOWN = 300  # 5 phút giữa các lần recovery
SCHEDULED_MAINTENANCE_INTERVAL = 21600  # 6 tiếng
MAX_CACHE_AGE_DAYS = 7  # Xóa cache cũ hơn 7 ngày
```

### Error Patterns

Các pattern lỗi được tự động phát hiện:

-   `403_forbidden`: 403, forbidden, server returned 403
-   `rate_limit`: rate limit, too many requests
-   `extraction_error`: unable to extract, error opening input file

## Hoạt động

### Khi phát hiện lỗi:

1. **Check cooldown**: Kiểm tra có trong thời gian cooldown không
2. **Classify error**: Phân loại loại lỗi (403, rate limit, etc.)
3. **Perform recovery**: Thực hiện các bước recovery tương ứng
4. **Update stats**: Cập nhật thống kê và timestamp

### Recovery process:

1. 🧹 **Clear yt-dlp cache** (`~/.cache/yt-dlp/`)
2. 🤖 **Clear bot cache** (`cache/songs/`)
3. 🔄 **Update yt-dlp** (if needed)
4. ✅ **Log completion** và cập nhật stats

### Scheduled maintenance:

-   Chạy tự động mỗi 6 tiếng
-   Cleanup cache files cũ (> 7 ngày)
-   Update yt-dlp nếu cần (weekly)
-   Background process không ảnh hưởng performance

## Monitoring

### Logs

Tất cả hoạt động được log với format:

```
🚨 Detected 403_forbidden error, initiating auto-recovery...
🔄 Starting auto-recovery for 403_forbidden...
🧹 Clearing yt-dlp cache...
✅ Auto-recovery completed (#1)
```

### Stats tracking

-   `recovery_count`: Tổng số lần recovery
-   `last_recovery_time`: Timestamp recovery cuối
-   `auto_recovery_enabled`: Trạng thái enable/disable
-   `cooldown_remaining`: Thời gian cooldown còn lại

## Integration

### Processing service

Auto-recovery được tích hợp vào `processing.py`:

```python
# Automatic recovery on YouTube errors
if "403" in str(e) or "forbidden" in str(e).lower():
    await auto_recovery_service.check_and_recover_if_needed(str(e))
```

### Main bot

Scheduled maintenance được khởi động trong `music_bot.py`:

```python
async def _run_scheduled_maintenance(self):
    while True:
        await asyncio.sleep(SCHEDULED_MAINTENANCE_INTERVAL)
        await auto_recovery_service.scheduled_maintenance()
```

## Lợi ích

✅ **Tự động hóa hoàn toàn**: Không cần can thiệp thủ công  
✅ **Phản hồi nhanh**: Phát hiện và xử lý lỗi ngay lập tức  
✅ **Cooldown protection**: Ngăn recovery quá thường xuyên  
✅ **Comprehensive logging**: Theo dõi đầy đủ hoạt động  
✅ **Proactive maintenance**: Bảo trì định kỳ tự động  
✅ **Zero downtime**: Không ảnh hưởng đến trải nghiệm người dùng

## Troubleshooting

### Nếu auto-recovery không hoạt động:

1. Kiểm tra logs để xem có error detection không
2. Verify cooldown period (5 phút)
3. Check auto-recovery enabled status
4. Xem scheduled maintenance có chạy không

### Manual override:

```python
# Disable auto-recovery nếu cần
auto_recovery_service.disable_auto_recovery()

# Enable lại
auto_recovery_service.enable_auto_recovery()
```
