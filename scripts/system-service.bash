sudo cat > /etc/systemd/system/music-bot.service <<EOF

[Unit]
Description=Discord Music Bot
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/pi/discord-music-bot
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF


# Enable service
sudo systemctl enable music-bot.service
sudo systemctl start music-bot.service