import subprocess
import asyncio
from urllib.parse import urlsplit, urlunsplit
import os
import json

from dotenv import load_dotenv

load_dotenv()


def _normalize_spotify_url(url: str) -> str:
    parts = urlsplit(url)
    # strip query/fragment for stability
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


async def spotdl_save_async(save_file: str, *urls: str):
    if not save_file.endswith(".spotdl"):
        save_file = f"{save_file}.spotdl"

    normalized = [_normalize_spotify_url(u) for u in urls if u]

    process = await asyncio.create_subprocess_exec(
        "spotdl",
        "save",
        *normalized,
        "--save-file",
        save_file,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode,
            ["spotdl", "save", *normalized, "--save-file", save_file],
            output=stdout,
            stderr=stderr,
        )

    return stdout.decode()


def spotdl_add_to_sync_file(save_file: str, url: str, output_dir: str) -> bool:
    """Add a new song URL to existing sync file or create new one"""
    if not save_file.endswith(".spotdl"):
        save_file = f"{save_file}.spotdl"

    normalized_url = _normalize_spotify_url(url)

    # Check if file exists
    if os.path.exists(save_file):
        try:
            with open(save_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            data = {"type": "sync", "query": [], "songs": []}
    else:
        data = {"type": "sync", "query": [], "songs": []}

    # Ensure correct sync format (convert array format if needed)
    if isinstance(data, list):
        # Convert old array format to sync format
        data = {"type": "sync", "query": [], "songs": data}
    elif "type" not in data:
        data = {"type": "sync", "query": [], "songs": []}

    # Add URL if not already exists
    if normalized_url not in data["query"]:
        data["query"].append(normalized_url)

        # Use spotdl to get song metadata
        try:
            cmd = ["spotdl", "save", normalized_url, "--save-file", f"{save_file}.temp"]
            subprocess.run(cmd, check=True, capture_output=True)

            # Read the temporary file to get song data
            with open(f"{save_file}.temp", "r", encoding="utf-8") as f:
                temp_data = json.load(f)

            if isinstance(temp_data, list) and temp_data:
                data["songs"].extend(temp_data)
            elif "songs" in temp_data:
                data["songs"].extend(temp_data["songs"])

            # Clean up temp file
            os.remove(f"{save_file}.temp")

        except subprocess.CalledProcessError:
            # If spotdl fails, still add the URL to query for later sync
            pass

        # Save updated file
        with open(save_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        return True

    return False


def spotdl_download_from_tracking(save_file: str, output_dir: str):
    subprocess.run(
        ["spotdl", "download", "--save-file", save_file, "--output", output_dir],
        check=True,
    )


def spotdl_sync_from_tracking(save_file: str, output_dir: str):
    subprocess.run(
        ["spotdl", "sync", "--save-file", save_file, "--output", output_dir],
        check=True,
    )


async def spotdl_download_from_tracking_async(save_file: str, output_dir: str):
    """Async version của spotdl download để không block event loop"""
    process = await asyncio.create_subprocess_exec(
        "spotdl",
        "download",
        "--save-file",
        save_file,
        "--output",
        output_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode,
            ["spotdl", "download", "--save-file", save_file, "--output", output_dir],
            output=stdout,
            stderr=stderr,
        )

    return stdout.decode()


async def spotdl_sync_from_tracking_async(save_file: str, output_dir: str):
    """Async version của spotdl sync với bảo vệ format sync"""
    # Backup original file format
    original_data = None
    backup_path = f"{save_file}.backup"

    try:
        # Read and backup original sync format
        if os.path.exists(save_file):
            with open(save_file, "r", encoding="utf-8") as f:
                original_data = json.load(f)

            # Create backup
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(original_data, f, indent=4, ensure_ascii=False)

        process = await asyncio.create_subprocess_exec(
            "spotdl",
            "sync",
            "--save-file",
            save_file,
            "--output",
            output_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode,
                ["spotdl", "sync", "--save-file", save_file, "--output", output_dir],
                output=stdout,
                stderr=stderr,
            )

        # Restore sync format if spotdl changed it
        await _restore_sync_format(save_file, original_data)

        return stdout.decode()

    finally:
        # Clean up backup file
        if os.path.exists(backup_path):
            os.remove(backup_path)


async def _restore_sync_format(save_file: str, original_data: dict) -> None:
    """Restore sync format if spotdl converted it to array format"""
    if not original_data or not os.path.exists(save_file):
        return

    try:
        # Check if file was converted to array format
        with open(save_file, "r", encoding="utf-8") as f:
            current_data = json.load(f)

        # If spotdl converted sync format to array, restore it
        if isinstance(current_data, list) and isinstance(original_data, dict):
            if original_data.get("type") == "sync":
                # Restore sync format with updated songs
                restored_data = {
                    "type": "sync",
                    "query": original_data.get("query", []),
                    "songs": (
                        current_data if current_data else original_data.get("songs", [])
                    ),
                }

                with open(save_file, "w", encoding="utf-8") as f:
                    json.dump(restored_data, f, indent=4, ensure_ascii=False)

    except Exception as e:
        # If restore fails, log but don't crash
        import logging

        logger = logging.getLogger("lofi-music")
        logger.warning(f"Failed to restore sync format for {save_file}: {e}")


async def spotdl_download_single_song_async(spotify_url: str, output_dir: str):
    """Download single song directly from Spotify URL để nhanh hơn"""
    normalized_url = _normalize_spotify_url(spotify_url)

    process = await asyncio.create_subprocess_exec(
        "spotdl",
        "download",
        normalized_url,
        "--output",
        output_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode,
            ["spotdl", "download", normalized_url, "--output", output_dir],
            output=stdout,
            stderr=stderr,
        )

    return stdout.decode()


def fix_playlist_format(save_file: str) -> bool:
    """Fix playlist file format from array to sync format"""
    if not os.path.exists(save_file):
        return False

    try:
        with open(save_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # If it's already in sync format, no need to fix
        if isinstance(data, dict) and data.get("type") == "sync":
            return True

        # If it's in array format, convert to sync format
        if isinstance(data, list):
            sync_data = {"type": "sync", "query": [], "songs": data}

            with open(save_file, "w", encoding="utf-8") as f:
                json.dump(sync_data, f, indent=4, ensure_ascii=False)

            return True

    except Exception as e:
        print(f"Error fixing format for {save_file}: {e}")
        return False

    return False
