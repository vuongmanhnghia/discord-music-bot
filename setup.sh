#!/bin/bash

# Tạo các thư mục cần thiết
mkdir -p lavalink/plugins

# Đặt quyền cho thư mục lavalink (user 322 trong container lavalink)
sudo chown -R 322:322 lavalink/

# Hoặc nếu không có quyền sudo, có thể dùng:
# chmod -R 777 lavalink/

echo "✅ Đã tạo thư mục và đặt quyền cho Lavalink"
echo "Bây giờ bạn có thể chạy: docker-compose up -d"