{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    go
    libsodium
    libopus
    ffmpeg
    yt-dlp
    pkg-config
  ];
  
  shellHook = ''
    echo "🎵 Discord Music Bot Dev Environment"
    echo "=================================="
    echo "✅ Go: $(go version)"
    echo "✅ FFmpeg: $(ffmpeg -version | head -1)"
    echo "✅ yt-dlp: $(yt-dlp --version)"
    echo "✅ libsodium: Available"
    echo "✅ opus: Available"
    echo ""
    echo "Run: go run cmd/bot/main.go"
  '';
}
