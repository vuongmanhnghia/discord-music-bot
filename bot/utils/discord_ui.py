"""Discord UI utilities - Embeds, Pagination, Progress, Interactions"""

import asyncio
import discord
from discord.ui import Button, View
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime
from ..pkg.logger import logger
from ..utils.async_processor import ProcessingTask, ProcessingStatus


class EmbedFactory:
    """Factory for creating Discord embeds with consistent styling"""
    
    @staticmethod
    def empty_state(title: str, description: str, suggestions: List[str], footer: str, color=discord.Color.blue()) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        if suggestions:
            embed.add_field(name="Gợi ý", value="\n".join([f"▸ {s}" for s in suggestions]), inline=False)
        embed.set_footer(text=footer)
        return embed
    
    @staticmethod
    def success(title: str, description: str, details: Optional[Dict[str, str]] = None, footer: Optional[str] = None, color=discord.Color.green()) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        if details:
            for name, value in details.items():
                embed.add_field(name=name, value=value, inline=False)
        if footer:
            embed.set_footer(text=footer)
        return embed
    
    @staticmethod
    def error(title: str, description: str, error_details: Optional[str] = None, suggestions: Optional[List[str]] = None, footer: str = "Vui lòng thử lại hoặc liên hệ admin nếu lỗi vẫn tiếp tục", color=discord.Color.red()) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        if error_details:
            embed.add_field(name="Chi tiết lỗi", value=f"```{error_details}```", inline=False)
        if suggestions:
            embed.add_field(name="Cách khắc phục", value="\n".join([f"▸ {s}" for s in suggestions]), inline=False)
        embed.set_footer(text=footer)
        return embed
    
    @staticmethod
    def info(title: str, description: str, info_fields: Optional[Dict[str, str]] = None, footer: Optional[str] = None, color=discord.Color.blue()) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        if info_fields:
            for name, value in info_fields.items():
                embed.add_field(name=name, value=value, inline=False)
        if footer:
            embed.set_footer(text=footer)
        return embed
    
    @staticmethod
    def warning(title: str, description: str, warning_details: Optional[str] = None, suggestions: Optional[List[str]] = None, footer: Optional[str] = None, color=discord.Color.orange()) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        if warning_details:
            embed.add_field(name="Chi tiết", value=warning_details, inline=False)
        if suggestions:
            embed.add_field(name="Khuyến nghị", value="\n".join([f"▸ {s}" for s in suggestions]), inline=False)
        if footer:
            embed.set_footer(text=footer)
        return embed
    
    @staticmethod
    def music(title: str, description: str, song_info: Optional[Dict[str, str]] = None, player_controls: Optional[str] = None, footer: Optional[str] = None, thumbnail: Optional[str] = None, color=discord.Color.purple()) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        if song_info:
            for name, value in song_info.items():
                embed.add_field(name=name, value=value, inline=True)
        if player_controls:
            embed.add_field(name="Điều khiển", value=player_controls, inline=False)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        if footer:
            embed.set_footer(text=footer)
        return embed


class PaginationView(View):
    """Interactive pagination with navigation buttons"""
    
    def __init__(self, pages: List[discord.Embed], author_id: int, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.author_id = author_id
        self.current_page = 0
        self.message: Optional[discord.Message] = None
        self._update_buttons()
    
    def _update_buttons(self):
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == 0
        self.children[3].disabled = self.current_page >= len(self.pages) - 1
        self.children[4].disabled = self.current_page >= len(self.pages) - 1
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Chỉ người dùng lệnh mới có thể điều khiển!", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.primary)
    async def first_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary)
    async def previous_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.danger)
    async def delete_message(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if self.message:
            try:
                await self.message.delete()
            except discord.NotFound:
                pass
    
    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.primary)
    async def last_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = len(self.pages) - 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


class Paginator:
    """Helper for creating paginated embeds"""
    
    @staticmethod
    def create_pages(items: List[dict], items_per_page: int, create_embed_func: Callable[[List[dict], int, int], discord.Embed], title: str) -> List[discord.Embed]:
        if not items:
            return [discord.Embed(title=title, description="Không có dữ liệu để hiển thị", color=discord.Color.greyple())]
        
        total_pages = (len(items) + items_per_page - 1) // items_per_page
        pages = []
        
        for page_num in range(total_pages):
            start_idx = page_num * items_per_page
            end_idx = min(start_idx + items_per_page, len(items))
            page_items = items[start_idx:end_idx]
            embed = create_embed_func(page_items, page_num + 1, total_pages)
            pages.append(embed)
        
        return pages
    
    @staticmethod
    def create_queue_embed(songs: List[dict], page_num: int, total_pages: int, current_song: Optional[dict] = None, queue_position: tuple = (0, 0)) -> discord.Embed:
        embed = discord.Embed(title="Hàng đợi phát nhạc", color=discord.Color.blue())
        
        if current_song:
            current_title = current_song.get("title", "Unknown")
            embed.add_field(name="Đang phát", value=f"**{current_title}**\n`Vị trí: {queue_position[0]}/{queue_position[1]}`", inline=False)
        
        if songs:
            songs_text = ""
            for i, song in enumerate(songs, 1):
                actual_pos = (page_num - 1) * 10 + i + queue_position[0]
                title = song.get("title", song.get("display_name", "Unknown"))
                if len(title) > 50:
                    title = title[:47] + "..."
                
                status = song.get("status", "unknown")
                status_indicators = {"ready": "", "processing": "○", "failed": "×", "pending": "·"}.get(status, "?")
                songs_text += f"{actual_pos}. {status_indicators} **{title}**\n"
            
            embed.add_field(name=f"Danh sách ({len(songs)} bài)", value=songs_text or "Trống", inline=False)
        
        embed.set_footer(text=f"Trang {page_num}/{total_pages} • Tổng {queue_position[1]} bài")
        return embed
    
    @staticmethod
    def create_playlist_embed(songs: List[dict], page_num: int, total_pages: int, playlist_name: str, total_songs: int) -> discord.Embed:
        embed = discord.Embed(title=f"Playlist: {playlist_name}", color=discord.Color.green())
        
        if songs:
            songs_text = ""
            start_idx = (page_num - 1) * 10
            
            for i, song in enumerate(songs, 1):
                actual_pos = start_idx + i
                title = song.get("title", song.get("input", "Unknown"))
                source = song.get("source_type", "Unknown")
                if len(title) > 50:
                    title = title[:47] + "..."
                songs_text += f"`{actual_pos}.` **{title}** `({source})`\n"
            
            embed.add_field(name="Nội dung", value=songs_text or "Trống", inline=False)
        
        embed.set_footer(text=f"Trang {page_num}/{total_pages} • Tổng cộng {total_songs} bài")
        return embed


async def send_paginated_embed(interaction: discord.Interaction, pages: List[discord.Embed], ephemeral: bool = False) -> Optional[discord.Message]:
    """Send paginated embed with navigation"""
    if not pages:
        await interaction.response.send_message("Không có dữ liệu để hiển thị", ephemeral=True)
        return None
    
    if len(pages) == 1:
        await interaction.response.send_message(embed=pages[0], ephemeral=ephemeral)
        return None
    
    view = PaginationView(pages=pages, author_id=interaction.user.id)
    await interaction.response.send_message(embed=pages[0], view=view, ephemeral=ephemeral)
    message = await interaction.original_response()
    view.message = message
    return message


class ProgressTracker:
    """Real-time progress updates for async processing"""
    
    def __init__(self):
        self.active_messages: Dict[str, discord.Message] = {}
        self.update_lock = asyncio.Lock()
    
    async def create_initial_progress(self, interaction: discord.Interaction, task: ProcessingTask, guild_id: int = None) -> Optional[discord.Message]:
        try:
            embed = self._create_progress_embed(task)
            
            if interaction.response.is_done():
                message = await interaction.followup.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)
                message = await interaction.original_response()
            
            self.active_messages[task.id] = message
            
            if message and task.song and task.song.id and guild_id:
                from ..utils.events import message_update_manager
                await message_update_manager.track_message(message, task.song.id, guild_id, "processing")
            
            return message
        except Exception as e:
            logger.error(f"Error creating initial progress for task {task.id}: {e}")
            return None
    
    async def update_progress(self, task: ProcessingTask):
        async with self.update_lock:
            try:
                message = self.active_messages.get(task.id)
                if not message:
                    return
                
                embed = self._create_progress_embed(task)
                await message.edit(embed=embed)
                
                if task.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.CANCELLED]:
                    await asyncio.sleep(5)
                    if task.id in self.active_messages:
                        del self.active_messages[task.id]
            except discord.NotFound:
                if task.id in self.active_messages:
                    del self.active_messages[task.id]
            except Exception as e:
                logger.error(f"Error updating progress for task {task.id}: {e}")
    
    def _create_progress_embed(self, task: ProcessingTask) -> discord.Embed:
        status_config = {
            ProcessingStatus.QUEUED: {"color": discord.Color.orange(), "emoji": "⏳", "title": "Queued for Processing"},
            ProcessingStatus.PROCESSING: {"color": discord.Color.blue(), "emoji": "🔄", "title": "Processing Song"},
            ProcessingStatus.COMPLETED: {"color": discord.Color.green(), "emoji": "✅", "title": "Processing Complete"},
            ProcessingStatus.FAILED: {"color": discord.Color.red(), "emoji": "❌", "title": "Processing Failed"},
            ProcessingStatus.CANCELLED: {"color": discord.Color.dark_grey(), "emoji": "⏹️", "title": "Processing Cancelled"},
        }
        
        config = status_config.get(task.status, status_config[ProcessingStatus.QUEUED])
        embed = discord.Embed(title=f"{config['emoji']} {config['title']}", description=f"**{task.song.original_input}**", color=config["color"], timestamp=datetime.now())
        
        if task.status == ProcessingStatus.PROCESSING:
            progress_bar = self._create_progress_bar(task.progress)
            embed.add_field(name="📊 Progress", value=f"{progress_bar} {task.progress}%", inline=False)
            stage = self._get_processing_stage(task.progress)
            if stage:
                embed.add_field(name="🎯 Current Stage", value=stage, inline=True)
        
        embed.add_field(name="🏷️ Task Info", value=f"**ID**: `{task.id}`\n**Priority**: {task.priority.name}\n**Requested**: <t:{int(task.created_at.timestamp())}:R>", inline=True)
        
        if task.status == ProcessingStatus.FAILED and task.retry_count > 0:
            embed.add_field(name="🔄 Retry Info", value=f"**Attempts**: {task.retry_count}/{task.max_retries}\n**Error**: {task.error_message or 'Unknown error'}", inline=False)
        
        if task.status == ProcessingStatus.FAILED and task.retry_count >= task.max_retries:
            embed.add_field(name="💀 Final Error", value=task.error_message or "Unknown error", inline=False)
        
        embed.set_footer(text=f"Task: {task.id}")
        return embed
    
    def _create_progress_bar(self, progress: int, length: int = 20) -> str:
        filled = int(length * progress / 100)
        empty = length - filled
        
        if progress == 100:
            fill_char = "🟩"
        elif progress >= 75:
            fill_char = "🟦"
        elif progress >= 50:
            fill_char = "🟨"
        elif progress >= 25:
            fill_char = "🟧"
        else:
            fill_char = "🟥"
        
        return f"{''.join([fill_char] * filled)}{''.join(['⬜'] * empty)}"
    
    def _get_processing_stage(self, progress: int) -> Optional[str]:
        if progress < 20:
            return "🔍 Validating URL..."
        elif progress < 40:
            return "📝 Extracting metadata..."
        elif progress < 60:
            return "📥 Downloading audio info..."
        elif progress < 80:
            return "🎵 Processing audio stream..."
        elif progress < 90:
            return "✨ Finalizing..."
        elif progress < 100:
            return "🎯 Almost done..."
        else:
            return "✅ Complete!"


progress_tracker = ProgressTracker()


async def create_initial_progress_message(interaction: discord.Interaction, task: ProcessingTask) -> Optional[discord.Message]:
    return await progress_tracker.create_initial_progress(interaction, task)


async def send_discord_progress_update(bot_instance, task: ProcessingTask):
    try:
        await progress_tracker.update_progress(task)
    except Exception as e:
        logger.error(f"Error sending Discord progress update: {e}")


class EnhancedProgressCallback:
    """Enhanced progress callback with Discord integration"""
    
    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.progress_message: Optional[discord.Message] = None
    
    async def __call__(self, task: ProcessingTask):
        try:
            if not self.progress_message and task.progress <= 10:
                self.progress_message = await create_initial_progress_message(self.interaction, task)
            
            if self.progress_message:
                await progress_tracker.update_progress(task)
            
            if task.status == ProcessingStatus.COMPLETED:
                await self._send_completion_notification(task)
            elif task.status == ProcessingStatus.FAILED and task.retry_count >= task.max_retries:
                await self._send_failure_notification(task)
        except Exception as e:
            logger.error(f"Error in enhanced progress callback: {e}")
    
    async def _send_completion_notification(self, task: ProcessingTask):
        try:
            embed = discord.Embed(title="🎵 Song Ready!", description=f"**{task.song.original_input}** is now ready to play!", color=discord.Color.green())
            await self.interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error sending completion notification: {e}")
    
    async def _send_failure_notification(self, task: ProcessingTask):
        try:
            embed = discord.Embed(title="❌ Processing Failed", description=f"Could not process **{task.song.original_input}**", color=discord.Color.red())
            if task.error_message:
                embed.add_field(name="Error Details", value=task.error_message, inline=False)
            await self.interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error sending failure notification: {e}")


class InteractionManager:
    """Prevent Discord interaction timeouts for long operations"""
    
    @staticmethod
    async def handle_long_operation(interaction: discord.Interaction, operation_func: Callable, initial_message: str = None, *args, **kwargs) -> Any:
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
                logger.debug(f"Deferred interaction for {interaction.command.name if interaction.command else 'unknown'}")
            
            result = await operation_func(*args, **kwargs)
            
            if isinstance(result, discord.Embed):
                await interaction.followup.send(embed=result)
            elif isinstance(result, str):
                await interaction.followup.send(result)
            else:
                await interaction.followup.send(str(result))
            
            return result
        except Exception as e:
            logger.error(f"Error in long operation: {e}")
            error_msg = f"❌ Operation failed: {str(e)[:100]}..."
            
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(error_msg, ephemeral=True)
                else:
                    await interaction.response.send_message(error_msg, ephemeral=True)
            except discord.HTTPException:
                logger.error("Failed to send error message - interaction may be expired")
            
            raise
    
    @staticmethod
    async def safe_response(interaction: discord.Interaction, content: str = None, embed: discord.Embed = None, ephemeral: bool = False):
        try:
            if interaction.response.is_done():
                await interaction.followup.send(content=content, embed=embed, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
        except discord.HTTPException as e:
            logger.error(f"Failed to send response: {e}")


# Backward compatibility helper functions for modern_embeds.py
def create_pause_embed() -> discord.Embed:
    return EmbedFactory.info("Tạm dừng", "Đã tạm dừng phát nhạc.", info_fields={"Điều khiển": "▸ `/resume` - Tiếp tục phát\n▸ `/stop` - Dừng hẳn"}, footer="Nhạc sẽ được giữ nguyên cho đến khi bạn resume hoặc stop")

def create_resume_embed() -> discord.Embed:
    return EmbedFactory.success("Tiếp tục phát", "Đã tiếp tục phát nhạc.", details={"Điều khiển": "▸ `/pause` - Tạm dừng\n▸ `/skip` - Bỏ qua bài"}, footer="Đang phát nhạc...")

def create_stop_embed() -> discord.Embed:
    return EmbedFactory.info("Đã dừng phát nhạc", "Hàng đợi đã được xóa.", info_fields={"Gợi ý": "▸ `/play [bài hát]` - Phát nhạc mới\n▸ `/playlist load [tên]` - Tải playlist"}, footer="Dùng /play để bắt đầu lại")

def create_skip_embed(song_title: str) -> discord.Embed:
    return EmbedFactory.success("Đã bỏ qua bài hát", f"**{song_title}**", details={"Tiếp theo": "Đang chuyển sang bài tiếp theo..."}, footer="Dùng /now để xem bài đang phát")

def create_volume_embed(volume: int) -> discord.Embed:
    if volume == 0:
        level, icon = "Tắt tiếng", "🔇"
    elif volume <= 33:
        level, icon = "Thấp", "🔉"
    elif volume <= 66:
        level, icon = "Trung bình", "🔊"
    else:
        level, icon = "Cao", "🔊"
    
    bar_length = 20
    filled = int(volume / 100 * bar_length)
    volume_bar = f"[{'█' * filled}{'░' * (bar_length - filled)}]"
    
    return EmbedFactory.success(f"{icon} Âm lượng đã đặt", f"**{volume}%** ({level})\n\n{volume_bar}", details={"Mức": f"{level} - {volume}%"}, footer="Dùng /volume [0-100] để thay đổi âm lượng")

def create_repeat_mode_embed(mode: str) -> discord.Embed:
    mode_config = {
        "off": {"icon": "📴", "name": "Tắt lặp", "description": "Phát hết hàng đợi rồi dừng", "detail": "Các bài sẽ phát một lần duy nhất"},
        "track": {"icon": "🔂", "name": "Lặp bài hiện tại", "description": "Lặp lại bài đang phát", "detail": "Bài này sẽ được lặp lại liên tục"},
        "queue": {"icon": "🔁", "name": "Lặp hàng đợi", "description": "Lặp lại toàn bộ hàng đợi", "detail": "Quay lại đầu hàng đợi sau khi phát hết"}
    }
    config = mode_config.get(mode, mode_config["off"])
    return EmbedFactory.success(f"{config['icon']} Chế độ lặp", f"**{config['name']}**\n\n{config['description']}", details={"Chi tiết": config["detail"]}, footer="Dùng /repeat để thay đổi chế độ lặp")

def create_already_paused_embed() -> discord.Embed:
    return EmbedFactory.info("Nhạc đã tạm dừng rồi", "Nhạc hiện đang trong trạng thái tạm dừng.", info_fields={"Gợi ý": "▸ `/resume` - Tiếp tục phát\n▸ `/stop` - Dừng hẳn và xóa queue"}, footer="Dùng /resume để tiếp tục")

def create_already_playing_embed() -> discord.Embed:
    return EmbedFactory.info("Nhạc đang phát rồi", "Nhạc hiện đang được phát.", info_fields={"Gợi ý": "▸ `/pause` - Tạm dừng\n▸ `/skip` - Bỏ qua bài\n▸ `/now` - Xem thông tin bài hát"}, footer="Nhạc đang phát...")

def create_shuffle_embed(total_songs: int) -> discord.Embed:
    return EmbedFactory.success("🔀 Đã xáo trộn queue", f"Queue đã được shuffle với **{total_songs}** bài hát.", details={"Lưu ý": "Bài đang phát không bị ảnh hưởng", "Tiếp theo": "Các bài tiếp theo đã được sắp xếp ngẫu nhiên"}, footer="Dùng /queue để xem thứ tự mới")

def create_shuffle_failed_embed(reason: str) -> discord.Embed:
    return EmbedFactory.error("Không thể shuffle queue", reason, suggestions=["Thêm nhiều bài hát vào queue bằng `/play` hoặc `/aplay`", "Kiểm tra queue hiện tại bằng `/queue`"], footer="Cần ít nhất 2 bài trong queue để shuffle")

def create_empty_queue_embed() -> discord.Embed:
    return EmbedFactory.empty_state("Hàng đợi trống", "Hiện tại chưa có bài hát nào trong hàng đợi.", ["Sử dụng `/play [tên bài/URL]` để thêm bài hát", "Tải playlist với `/playlist load [tên]`", "Xem playlist có sẵn với `/playlist list`"], "Bắt đầu phát nhạc ngay!")

def create_playlist_created_embed(playlist_name: str) -> discord.Embed:
    return EmbedFactory.success("Playlist đã tạo", f"Playlist **{playlist_name}** đã được tạo thành công!", details={"Tiếp theo": f"▸ Thêm bài hát bằng `/playlist add {playlist_name} [URL]`\n▸ Tải playlist bằng `/playlist load {playlist_name}`"}, footer="Playlist trống, hãy thêm bài hát vào!")

def create_playlist_deleted_embed(playlist_name: str, song_count: int) -> discord.Embed:
    return EmbedFactory.success("Playlist đã xóa", f"Playlist **{playlist_name}** ({song_count} bài) đã được xóa.", footer="Playlist đã được xóa vĩnh viễn")

def create_song_added_to_playlist_embed(playlist_name: str, song_title: str, total_songs: int) -> discord.Embed:
    return EmbedFactory.success("Đã thêm vào playlist", f"**{song_title}**", details={"Playlist": playlist_name, "Tổng số bài": str(total_songs)}, footer=f"Dùng /playlist load {playlist_name} để phát")

def create_song_removed_from_playlist_embed(playlist_name: str, song_title: str, remaining: int) -> discord.Embed:
    return EmbedFactory.success("Đã xóa khỏi playlist", f"**{song_title}**", details={"Playlist": playlist_name, "Còn lại": f"{remaining} bài"}, footer=f"Playlist {playlist_name} đã được cập nhật")

def create_playlist_loaded_embed(playlist_name: str, song_count: int, success_count: int, failed_count: int) -> discord.Embed:
    description = f"Đã thêm **{success_count}/{song_count}** bài hát vào hàng đợi"
    details = {"Playlist": playlist_name, "Thành công": str(success_count)}
    if failed_count > 0:
        details["Thất bại"] = str(failed_count)
    return EmbedFactory.success("Đã tải playlist", description, details=details, footer="Các bài hát đang được xử lý...")

def create_no_playlists_found_embed() -> discord.Embed:
    return EmbedFactory.empty_state("Không có playlist", "Bạn chưa tạo playlist nào.", ["Tạo playlist mới với `/playlist create [tên]`", "Thêm bài hát với `/playlist add [tên] [URL]`"], "Bắt đầu tạo playlist ngay!")

def create_not_in_voice_embed() -> discord.Embed:
    return EmbedFactory.error("Không kết nối voice", "Bạn cần vào một voice channel trước!", suggestions=["Vào một voice channel trước khi sử dụng lệnh này"], footer="Bot sẽ tự động join voice channel của bạn")

def create_bot_not_playing_embed() -> discord.Embed:
    return EmbedFactory.error("Bot không phát nhạc", "Hiện tại bot không phát bài hát nào.", suggestions=["Dùng `/play [tên bài/URL]` để phát nhạc", "Dùng `/queue` để xem hàng đợi"], footer="Không có gì để điều khiển")

def create_playlist_not_found_embed(playlist_name: str) -> discord.Embed:
    return EmbedFactory.error("Playlist không tồn tại", f"Playlist **{playlist_name}** không tồn tại.", suggestions=["Dùng `/playlist list` để xem danh sách playlist", f"Tạo playlist mới với `/playlist create {playlist_name}`"], footer="Kiểm tra tên playlist")

def create_playlist_already_exists_embed(playlist_name: str) -> discord.Embed:
    return EmbedFactory.error("Playlist đã tồn tại", f"Playlist **{playlist_name}** đã tồn tại.", suggestions=["Chọn tên khác", f"Xem playlist bằng `/playlist view {playlist_name}`", f"Xóa playlist cũ bằng `/playlist delete {playlist_name}`"], footer="Tên playlist phải duy nhất")

def create_youtube_playlist_loading_embed(playlist_url: str) -> discord.Embed:
    return EmbedFactory.info("Đang tải YouTube playlist", f"Đang xử lý: {playlist_url}", info_fields={"Trạng thái": "🔄 Đang trích xuất danh sách video..."}, footer="Vui lòng đợi...")

def create_youtube_playlist_complete_embed(video_count: int, playlist_title: str) -> discord.Embed:
    return EmbedFactory.success("YouTube Playlist đã tải", f"Đã thêm **{video_count}** video từ playlist **{playlist_title}**", details={"Tổng video": str(video_count)}, footer="Các video đang được xử lý...")
