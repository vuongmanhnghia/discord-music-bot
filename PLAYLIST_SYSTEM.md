# Hệ thống Playlist - Discord Music Bot

Hệ thống playlist đã được triển khai với các tính năng chính sau:

## 🎵 Tính năng chính

### 1. Quản lý Playlist

-   **Tạo playlist**: `/create <tên>`
-   **Xem danh sách**: `/playlists`
-   **Xem chi tiết**: `/playlist <tên>`
-   **Xóa playlist**: `/delete <tên>`

### 2. Quản lý bài hát trong playlist

-   **Thêm bài**: `/add <playlist> <url/tên bài>`
-   **Xóa bài**: `/remove <playlist> <số thứ tự>`

### 3. Sử dụng playlist

-   **Nạp vào queue**: `/use <playlist>`

## 📁 Lưu trữ

-   Playlist được lưu trong thư mục `playlist/` dưới dạng file JSON
-   Mỗi playlist có metadata: tên, ngày tạo, ngày cập nhật
-   Mỗi entry có: input gốc, loại nguồn, title, ngày thêm

## 🔄 Luồng sử dụng

### Tạo và quản lý playlist:

```
/create "My Favorites"           # Tạo playlist mới
/add "My Favorites" "Never Gonna Give You Up"  # Thêm bài từ tìm kiếm
/add "My Favorites" "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Thêm từ URL
/playlist "My Favorites"         # Xem nội dung
```

### Phát nhạc từ playlist:

```
/join                           # Bot tham gia voice channel
/use "My Favorites"             # Nạp playlist vào queue
                               # Tự động bắt đầu phát nhạc
```

## 🏗️ Kiến trúc

### 1. Domain Layer

-   **PlaylistEntry**: Đơn vị cơ bản chứa thông tin bài hát
-   **Playlist**: Tập hợp các entry với metadata
-   **LibraryManager**: Quản lý tất cả playlist với caching

### 2. Repository Layer

-   **PlaylistRepository**: Xử lý persistence (JSON files)
-   Tự động tạo tên file an toàn từ tên playlist
-   Xử lý serialize/deserialize

### 3. Service Layer

-   **PlaylistService**: Business logic và integration với queue
-   Chuyển đổi PlaylistEntry thành Song objects
-   Validation và error handling

### 4. Presentation Layer

-   Discord slash commands với UI thân thiện
-   Embed messages với màu sắc phù hợp
-   Error handling và user feedback

## 🎯 Ưu điểm

1. **Clean Architecture**: Tách biệt rõ ràng các layer
2. **Persistent**: Playlist không bị mất khi restart bot
3. **Type Safety**: Sử dụng enums và type hints
4. **Caching**: LibraryManager cache playlist để tăng performance
5. **Error Handling**: Xử lý lỗi comprehensive với user-friendly messages
6. **Extensible**: Dễ dàng thêm tính năng mới (shuffle playlist, import/export, etc.)

## 🔧 Technical Details

-   JSON serialization với datetime support
-   Safe filename generation từ playlist names
-   Memory caching với automatic invalidation
-   Integration với existing queue system
-   Source type detection (YouTube, Spotify, Search, SoundCloud)
