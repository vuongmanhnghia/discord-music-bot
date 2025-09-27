# 🎵 Hệ thống Playlist - Discord- `/delete <tên>` - Xóa playlist

## 🚀 Tính năng Enhanced /play

Command `/play` hiện có 2 chế độ hoạt động:

-   **`/play`** (không tham số) - Tự động nạp thêm bài từ playlist hiện tại
-   **`/play <query>`** - Tìm kiếm/phát từ URL như truyền thống

Workflow thông minh:

1. Sử dụng `/use "My Playlist"` để chọn playlist
2. Sử dụng `/play` để tiếp tục nạp bài từ playlist đó
3. Hoặc `/play "bài mới"` để thêm bài từ nguồn khác

## 🎯 Tính năng Smart /add

Command `/add` hiện có 2 variants thông minh:

-   **`/add <song>`** - Thêm vào playlist hiện tại (đã được `/use`)
-   **`/addto <playlist> <song>`** - Thêm vào playlist chỉ định

Workflow tối ưu:

1. Sử dụng `/use "My Playlist"` để chọn playlist làm active
2. Sử dụng `/add "song1"`, `/add "song2"` liên tục
3. Hoặc `/addto "Other Playlist" "song"` để thêm vào playlist khác

## Tính năngsic Bot

## Cách sử dụng nhanh

### 1. Tạo và quản lý playlist

```bash
/create "My Playlist"           # Tạo playlist mới
/use "My Playlist"              # Chọn playlist làm playlist hiện tại
/add "Despacito"                # Thêm bài vào playlist hiện tại
/add "https://youtu.be/abc123"  # Thêm từ YouTube URL vào playlist hiện tại
/addto "Other Playlist" "Song"  # Thêm bài vào playlist chỉ định
/playlist "My Playlist"         # Xem nội dung playlist
/remove "My Playlist" 1         # Xóa bài số 1
/playlists                      # Liệt kê tất cả playlist
```

### 2. Phát playlist

```bash
/join                           # Bot tham gia voice channel
/use "My Playlist"              # Nạp playlist vào queue và bắt đầu phát
/play                           # Nạp thêm bài từ playlist hiện tại
/play "Despacito"               # Hoặc tìm kiếm bài mới như thường
```

### 3. Commands playlist đầy đủ

-   `/create <tên>` - Tạo playlist mới
-   `/use <playlist>` - Nạp playlist vào queue (và đặt làm playlist hiện tại)
-   `/add <bài hát>` - Thêm bài vào playlist hiện tại
-   `/addto <playlist> <bài hát>` - Thêm bài vào playlist chỉ định
-   `/remove <playlist> <số>` - Xóa bài khỏi playlist
-   `/playlist <tên>` - Hiển thị nội dung playlist
-   `/playlists` - Liệt kê tất cả playlist
-   `/delete <tên>` - Xóa playlist

## Tính năng

✅ **Lưu trữ vĩnh viễn** - Playlist được lưu trong file JSON  
✅ **Multi-source** - Hỗ trợ YouTube, Spotify, SoundCloud, tìm kiếm  
✅ **Quản lý dễ dàng** - Thêm, xóa, sửa playlist qua Discord commands  
✅ **Tích hợp queue** - Nạp playlist trực tiếp vào hàng đợi phát nhạc  
✅ **Smart /play** - `/play` không tham số tự động phát từ playlist hiện tại  
✅ **Smart /add** - `/add` thêm vào playlist hiện tại, `/addto` thêm vào playlist chỉ định  
✅ **Metadata đầy đủ** - Thời gian tạo, cập nhật, thông tin bài hát

## Demo

Chạy demo để test hệ thống:

```bash
python scripts/demo_playlist.py
```

Playlist được lưu trong thư mục `playlist/` dưới dạng JSON.
