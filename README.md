# Discord Music Bot 24/7

Discord music bot với khả năng phát nhạc 24/7 sử dụng Python, Lavalink, và Docker Compose.

## Tính năng

- ✅ Phát nhạc từ YouTube, SoundCloud, Bandcamp, Twitch, Vimeo
- ✅ Hỗ trợ YouTube playlist
- ✅ Hoạt động 24/7 với tự động kết nối lại
- ✅ Các lệnh cơ bản: play, pause, resume, skip, volume
- ✅ Auto-connect đến voice channel khi khởi động
- ✅ Tự động phát playlist liên tục

## Cài đặt

### Bước 1: Tạo Discord Bot

1. Truy cập [Discord Developer Portal](https://discord.com/developers/applications)
2. Tạo ứng dụng mới và bot
3. Copy Bot Token
4. Bật các intents cần thiết: `MESSAGE CONTENT INTENT`, `SERVER MEMBERS INTENT`
5. Invite bot vào server với quyền: `Send Messages`, `Connect`, `Speak`, `Use Voice Activity`

### Bước 2: Cấu hình

1. Copy file `.env.example` thành `.env`
2. Điền Discord Bot Token vào `DISCORD_TOKEN`
3. (Tùy chọn) Đặt ID của voice channel và text channel mặc định
4. (Tùy chọn) Đặt URL playlist YouTube mặc định

### Bước 3: Tạo thư mục và quyền

```bash
# Chạy script setup (Linux/Mac)
chmod +x setup.sh
./setup.sh

# Hoặc tạo thư mục thủ công
mkdir -p lavalink/plugins lavalink/logs
chmod -R 777 lavalink/
```

### Bước 4: Chạy Bot

```bash
# Khởi động với Docker Compose
docker-compose up -d

# Xem logs
docker-compose logs -f

# Dừng bot
docker-compose down
```

## Cấu trúc thư mục

```
discord-music-bot/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env
├── bot.py
├── config.py
├── lavalink/
│   └── application.yml
└── README.md
```

## Lệnh Bot

| Lệnh                        | Mô tả                      |
| --------------------------- | -------------------------- |
| `!join [channel]`           | Kết nối đến voice channel  |
| `!leave`                    | Rời khỏi voice channel     |
| `!play <tìm kiếm hoặc URL>` | Phát nhạc                  |
| `!playlist <URL>`           | Tải playlist               |
| `!skip`                     | Bỏ qua bài hát hiện tại    |
| `!pause`                    | Tạm dừng                   |
| `!resume`                   | Tiếp tục phát              |
| `!volume [0-100]`           | Điều chỉnh âm lượng        |
| `!now`                      | Hiển thị bài hát đang phát |

## Cấu hình nâng cao

### Auto-connect khi khởi động

Thêm vào file `.env`:

```
DEFAULT_VOICE_CHANNEL_ID=123456789012345678
DEFAULT_TEXT_CHANNEL_ID=123456789012345678
DEFAULT_PLAYLIST_URL=https://www.youtube.com/playlist?list=...
```

### Lấy Channel ID

1. Bật Developer Mode trong Discord (User Settings > Advanced)
2. Right-click vào channel > Copy ID

## Xử lý sự cố

### Bot không phát nhạc

- Kiểm tra Lavalink container có chạy không: `docker-compose logs lavalink`
- Đảm bảo bot có quyền Connect và Speak trong voice channel

### Lỗi kết nối Lavalink

- Kiểm tra port 2333 có bị chiếm không
- Restart containers: `docker-compose restart`

### Bot bị disconnect

- Bot có tính năng auto-reconnect mỗi 5 phút
- Kiểm tra logs để xem lỗi: `docker-compose logs discord-bot`

## Logs

```bash
# Xem logs của bot
docker-compose logs -f discord-bot

# Xem logs của Lavalink
docker-compose logs -f lavalink

# Xem logs của tất cả services
docker-compose logs -f
```

## Lưu ý

- Bot sử dụng Lavalink 4.x với YouTube plugin mới nhất
- Hỗ trợ playlist YouTube lên đến 100 tracks
- Tự động loop playlist khi hết bài
- Volume mặc định là 100%
- Prefix mặc định là `!`

## Yêu cầu hệ thống

- Docker và Docker Compose
- RAM: tối thiểu 512MB (khuyến nghị 1GB)
- CPU: 1 core
- Disk: 500MB trống
- Network: kết nối internet ổn định

## Bảo mật

- Không chia sẻ Discord Bot Token
- Đặt password mạnh cho Lavalink
- Sử dụng non-root user trong container
- Giới hạn quyền bot trong Discord server

# Project Structure

The project has been restructured for better maintainability:

```
discord-music-bot/
├── src/                    # Source code
│   ├── cogs/               # Discord bot command modules
│   │   └── music.py        # Music commands implementation
│   ├── utils/              # Utility modules
│   │   ├── logger.py       # Logging utility
│   │   └── player.py       # Music player implementation
│   └── main.py             # Main entry point
├── config.py               # Configuration settings
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # Docker Compose configuration
└── README.md               # This file
```

## Architecture

- `main.py`: Initializes the bot and loads cogs
- `cogs/music.py`: Contains all the bot commands and event handlers
- `utils/player.py`: Handles music playback logic
- `utils/logger.py`: Centralized logging configuration
- `config.py`: Stores bot configuration settings

## How to Run

From the project root directory:

```bash
# Install dependencies
pip install -r requirements.txt

# Start the bot
python src/main.py
```

Or use Docker:

```bash
docker-compose up -d
```
