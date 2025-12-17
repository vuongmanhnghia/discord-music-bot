package commands

import (
	"fmt"
	"strings"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
)

const (
	itemsPerPage = 10
)

// PaginationData holds pagination state
type PaginationData struct {
	CurrentPage int
	TotalPages  int
	TotalItems  int
	Items       []string
}

// createPaginationButtons creates navigation buttons for pagination
func createPaginationButtons(page, totalPages int, customIDPrefix string) []discordgo.MessageComponent {
	if totalPages <= 1 {
		return nil
	}

	buttons := []discordgo.MessageComponent{
		discordgo.Button{
			Label:    "⏮️", // First
			Style:    discordgo.SecondaryButton,
			CustomID: fmt.Sprintf("%s:first", customIDPrefix),
			Disabled: page == 0,
		},
		discordgo.Button{
			Label:    "◀️", // Previous
			Style:    discordgo.PrimaryButton,
			CustomID: fmt.Sprintf("%s:prev", customIDPrefix),
			Disabled: page == 0,
		},
		discordgo.Button{
			Label:    fmt.Sprintf("Page %d/%d", page+1, totalPages),
			Style:    discordgo.SecondaryButton,
			CustomID: fmt.Sprintf("%s:current:%d", customIDPrefix, page),
			Disabled: true,
		},
		discordgo.Button{
			Label:    "▶️", // Next
			Style:    discordgo.PrimaryButton,
			CustomID: fmt.Sprintf("%s:next", customIDPrefix),
			Disabled: page >= totalPages-1,
		},
		discordgo.Button{
			Label:    "⏭️", // Last
			Style:    discordgo.SecondaryButton,
			CustomID: fmt.Sprintf("%s:last", customIDPrefix),
			Disabled: page >= totalPages-1,
		},
	}

	return []discordgo.MessageComponent{
		discordgo.ActionsRow{
			Components: buttons,
		},
	}
}

// buildQueuePage builds a paginated queue display
func buildQueuePage(tracklist *entities.Tracklist, page int) (*discordgo.MessageEmbed, []discordgo.MessageComponent) {
	if tracklist == nil || tracklist.Size() == 0 {
		return NewEmbed().
			Title("Queue").
			Description("The queue is empty. Use `/play` to add songs!").
			Color(ColorInfo).
			Build(), nil
	}

	allSongs := tracklist.GetAllSongs()
	currentPos, _ := tracklist.Position()
	totalSongs := len(allSongs)
	totalPages := (totalSongs + itemsPerPage - 1) / itemsPerPage

	// Validate page number
	if page < 0 {
		page = 0
	}
	if page >= totalPages {
		page = totalPages - 1
	}

	builder := NewEmbed().
		Title(fmt.Sprintf("Music Queue (Page %d/%d)", page+1, totalPages)).
		Color(ColorPrimary)

	// Calculate range for this page
	start := page * itemsPerPage
	end := start + itemsPerPage
	if end > totalSongs {
		end = totalSongs
	}

	// Build song list
	var sb strings.Builder
	for i := start; i < end; i++ {
		song := allSongs[i]
		meta := song.GetMetadata()

		// Position indicator (1-based)
		position := i + 1
		indicator := fmt.Sprintf("`%2d.`", position)

		// Highlight current song
		if position == currentPos {
			indicator = fmt.Sprintf("`%2d.`", position) + " ►"
		}

		if meta != nil {
			title := meta.Title
			if len(title) > 50 {
				title = title[:47] + "..."
			}
			duration := meta.DurationFormatted()
			sb.WriteString(fmt.Sprintf("%s **%s** `[%s]`\n", indicator, title, duration))
		} else {
			songName := song.DisplayName()
			if len(songName) > 50 {
				songName = songName[:47] + "..."
			}
			sb.WriteString(fmt.Sprintf("%s **%s**\n", indicator, songName))
		}
	}

	builder.Description(sb.String())

	// Footer with stats
	repeatMode := tracklist.GetRepeatMode()
	repeatIcon := "🔁"
	if repeatMode == entities.RepeatModeNone {
		repeatIcon = "➡️"
	} else if repeatMode == entities.RepeatModeTrack {
		repeatIcon = "🔂"
	}

	builder.Footer(fmt.Sprintf("Total: %d songs • Showing %d-%d • Repeat: %s %s",
		totalSongs, start+1, end, repeatIcon, repeatMode))

	// Create pagination buttons
	buttons := createPaginationButtons(page, totalPages, "queue")

	return builder.Build(), buttons
}

// buildPlaylistPage builds a paginated playlist display
func buildPlaylistPage(playlistName string, entries []PlaylistEntry, page int) (*discordgo.MessageEmbed, []discordgo.MessageComponent) {
	if len(entries) == 0 {
		return NewEmbed().
			Title(fmt.Sprintf("📋 %s", playlistName)).
			Description("This playlist is empty").
			Color(ColorInfo).
			Footer("Use /playlist add to add songs").
			Build(), nil
	}

	totalItems := len(entries)
	totalPages := (totalItems + itemsPerPage - 1) / itemsPerPage

	// Validate page number
	if page < 0 {
		page = 0
	}
	if page >= totalPages {
		page = totalPages - 1
	}

	builder := NewEmbed().
		Title(fmt.Sprintf("📋 %s (Page %d/%d)", playlistName, page+1, totalPages)).
		Color(ColorPrimary)

	// Calculate range for this page
	start := page * itemsPerPage
	end := start + itemsPerPage
	if end > totalItems {
		end = totalItems
	}

	// Build song list
	var sb strings.Builder
	for i := start; i < end; i++ {
		entry := entries[i]
		position := i + 1

		title := entry.Title
		if title == "" {
			title = entry.OriginalInput
		}
		if len(title) > 50 {
			title = title[:47] + "..."
		}

		sb.WriteString(fmt.Sprintf("`%2d.` **%s**\n", position, title))
	}

	builder.Description(sb.String())
	builder.Footer(fmt.Sprintf("Total: %d songs • Showing %d-%d • Use /use %s to play",
		totalItems, start+1, end, playlistName))

	// Create pagination buttons with playlist name in custom ID
	buttons := createPaginationButtons(page, totalPages, fmt.Sprintf("playlist:%s", playlistName))

	return builder.Build(), buttons
}

// PlaylistEntry represents a playlist entry for pagination
type PlaylistEntry struct {
	Title         string
	OriginalInput string
}
