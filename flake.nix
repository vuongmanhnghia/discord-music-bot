{
  description = "Dev shell for Discord Music Bot";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python312;
        pyPkgs = pkgs.python312Packages;
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            python
            pyPkgs.pip
            pyPkgs.setuptools
            pyPkgs.wheel
            pkgs.go
            pkgs.yt-dlp
            pkgs.pkg-config
            pkgs.libsodium
            pkgs.libopus
            pkgs.opusfile
            pkgs.ffmpeg
          ];

          VENV_DIR = "./venv";
          
          # Enable CGO for gopus
          CGO_ENABLED = "1";
          
          # Set pkg-config paths for libopus, opusfile, and libsodium
          PKG_CONFIG_PATH = "${pkgs.libopus.dev}/lib/pkgconfig:${pkgs.opusfile.dev}/lib/pkgconfig:${pkgs.libsodium.dev}/lib/pkgconfig";

          shellHook = ''
            echo "🎵 Discord Music Bot (Go) Dev Environment"
            echo "========================================"
            echo "✅ Go: $(go version | cut -d' ' -f3)"
            echo "✅ FFmpeg: $(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f3)"
            echo "✅ yt-dlp: $(yt-dlp --version)"
            echo "✅ libsodium + libopus: Available"
            echo "✅ CGO_ENABLED: $CGO_ENABLED"
            echo ""
            echo "Run bot: go run cmd/bot/main.go"
            echo "Build:   go build -o bin/musicbot cmd/bot/main.go"
          '';
        };
      });
}
