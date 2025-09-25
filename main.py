import discord
import os
import glob
from dotenv import load_dotenv

from src.bot import MusicBot

load_dotenv()

# Opus library setup
opus_paths = [
    'libopus.so',
    'libopus.so.0',
    '/usr/lib/x86_64-linux-gnu/libopus.so.0',
    '/usr/lib/libopus.so.0'
]

# Thêm các đường dẫn từ Nix store nếu có
if 'NIX_STORE' in os.environ:
    nix_opus = glob.glob('/nix/store/*/lib/libopus.so*')
    opus_paths.extend(nix_opus)

opus_loaded = False
for path in opus_paths:
    try:
        discord.opus.load_opus(path)
        print(f"Loaded Opus from: {path}")
        opus_loaded = True
        break
    except (discord.opus.OpusNotLoaded, OSError):
        continue

if not opus_loaded:
    print("Warning: Could not load Opus library. Voice features may not work.")

# Main execution
if __name__ == "__main__":
    bot = MusicBot()
    bot.run_bot()