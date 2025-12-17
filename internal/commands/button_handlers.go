package commands

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/bwmarrin/discordgo"
)

// handleButtonInteraction handles pagination button clicks
func (h *Handler) handleButtonInteraction(s *discordgo.Session, i *discordgo.InteractionCreate) {
	customID := i.MessageComponentData().CustomID

	// Parse custom ID: "type:page" or "playlist:name:page"
	parts := strings.Split(customID, ":")
	if len(parts) < 2 {
		return
	}

	buttonType := parts[0]

	switch buttonType {
	case "queue":
		h.handleQueuePagination(s, i, parts)
	case "playlist":
		h.handlePlaylistPagination(s, i, parts)
	}
}

// handleQueuePagination handles queue pagination buttons
func (h *Handler) handleQueuePagination(s *discordgo.Session, i *discordgo.InteractionCreate, parts []string) {
	if len(parts) < 2 {
		return
	}

	action := parts[1]

	// Get tracklist
	tracklist := h.playbackService.GetTracklist(i.GuildID)
	if tracklist == nil {
		return
	}

	totalSongs := tracklist.Size()
	totalPages := (totalSongs + itemsPerPage - 1) / itemsPerPage

	// Calculate target page based on action
	var targetPage int
	switch action {
	case "first":
		targetPage = 0
	case "prev":
		// Need to find current page from the interaction message
		targetPage = h.getCurrentPageFromMessage(i)
		if targetPage > 0 {
			targetPage--
		}
	case "next":
		targetPage = h.getCurrentPageFromMessage(i)
		if targetPage < totalPages-1 {
			targetPage++
		}
	case "last":
		targetPage = totalPages - 1
	default:
		if strings.HasPrefix(action, "current:") {
			// Disabled button, ignore
			return
		}
		return
	}

	// Build the requested page
	embed, components := buildQueuePage(tracklist, targetPage)

	// Update the message
	err := s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseUpdateMessage,
		Data: &discordgo.InteractionResponseData{
			Embeds:     []*discordgo.MessageEmbed{embed},
			Components: components,
		},
	})

	if err != nil {
		h.logger.WithError(err).Error("Failed to update queue pagination")
	}
}

// getCurrentPageFromMessage extracts current page from the message embed
func (h *Handler) getCurrentPageFromMessage(i *discordgo.InteractionCreate) int {
	if len(i.Message.Embeds) == 0 {
		return 0
	}

	title := i.Message.Embeds[0].Title
	// Parse "Music Queue (Page X/Y)" or "📋 Playlist (Page X/Y)"
	if strings.Contains(title, "(Page ") {
		start := strings.Index(title, "(Page ") + 6
		end := strings.Index(title[start:], "/")
		if end > 0 {
			pageStr := title[start : start+end]
			page, err := strconv.Atoi(pageStr)
			if err == nil {
				return page - 1 // Convert to 0-indexed
			}
		}
	}
	return 0
}

// handlePlaylistPagination handles playlist pagination buttons
func (h *Handler) handlePlaylistPagination(s *discordgo.Session, i *discordgo.InteractionCreate, parts []string) {
	if len(parts) < 3 {
		return
	}

	playlistName := parts[1]
	action := parts[2]

	// Get playlist
	playlist, err := h.playlistService.GetPlaylistForGuild(i.GuildID, playlistName)
	if err != nil {
		h.logger.WithError(err).Error("Failed to get playlist for pagination")
		// Send error message
		_ = s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
			Type: discordgo.InteractionResponseChannelMessageWithSource,
			Data: &discordgo.InteractionResponseData{
				Content: fmt.Sprintf("Failed to load playlist: %v", err),
				Flags:   discordgo.MessageFlagsEphemeral,
			},
		})
		return
	}

	totalItems := len(playlist.Entries)
	totalPages := (totalItems + itemsPerPage - 1) / itemsPerPage

	// Calculate target page based on action
	var targetPage int
	switch action {
	case "first":
		targetPage = 0
	case "prev":
		targetPage = h.getCurrentPageFromMessage(i)
		if targetPage > 0 {
			targetPage--
		}
	case "next":
		targetPage = h.getCurrentPageFromMessage(i)
		if targetPage < totalPages-1 {
			targetPage++
		}
	case "last":
		targetPage = totalPages - 1
	default:
		if strings.HasPrefix(action, "current:") {
			// Disabled button, ignore
			return
		}
		return
	}

	// Convert to pagination format
	entries := make([]PlaylistEntry, len(playlist.Entries))
	for i, entry := range playlist.Entries {
		entries[i] = PlaylistEntry{
			Title:         entry.Title,
			OriginalInput: entry.OriginalInput,
		}
	}

	// Build the requested page
	embed, components := buildPlaylistPage(playlistName, entries, targetPage)

	// Update the message
	err = s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseUpdateMessage,
		Data: &discordgo.InteractionResponseData{
			Embeds:     []*discordgo.MessageEmbed{embed},
			Components: components,
		},
	})

	if err != nil {
		h.logger.WithError(err).Error("Failed to update playlist pagination")
	}
}
