package commands

import "github.com/bwmarrin/discordgo"

// GetCommands returns all slash command definitions
func GetCommands() []*discordgo.ApplicationCommand {
	return []*discordgo.ApplicationCommand{
		// Playback commands
		{
			Name:        "play",
			Description: "Play a song from YouTube URL or search query",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionString,
					Name:        "query",
					Description: "YouTube URL or search query",
					Required:    true,
				},
			},
		},
		{
			Name:        "aplay",
			Description: "Add all songs from a YouTube playlist to queue",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionString,
					Name:        "url",
					Description: "YouTube playlist URL",
					Required:    true,
				},
			},
		},
		{
			Name:        "pause",
			Description: "Pause the current playback",
		},
		{
			Name:        "resume",
			Description: "Resume paused playback",
		},
		{
			Name:        "skip",
			Description: "Skip to the next song or jump to a specific song by index",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionInteger,
					Name:        "index",
					Description: "Song index to skip to (1-based, optional)",
					Required:    false,
					MinValue:    func() *float64 { v := 1.0; return &v }(),
				},
			},
		},
		{
			Name:        "stop",
			Description: "Stop playback and clear the queue",
		},
		{
			Name:        "volume",
			Description: "Adjust playback volume (0-100%)",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionInteger,
					Name:        "level",
					Description: "Volume level (0-100)",
					Required:    true,
					MinValue:    func() *float64 { v := 0.0; return &v }(),
					MaxValue:    100,
				},
			},
		},

		// Queue commands
		{
			Name:        "queue",
			Description: "Display the current song queue",
		},
		{
			Name:        "nowplaying",
			Description: "Show information about the currently playing song",
		},
		{
			Name:        "shuffle",
			Description: "Shuffle the songs in queue",
		},
		{
			Name:        "clear",
			Description: "Clear the queue and reset playback state",
		},
		{
			Name:        "repeat",
			Description: "Configure repeat mode for playback",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionString,
					Name:        "mode",
					Description: "Repeat mode",
					Required:    true,
					Choices: []*discordgo.ApplicationCommandOptionChoice{
						{Name: "Off", Value: "none"},
						{Name: "Single Track", Value: "track"},
						{Name: "Entire Queue", Value: "queue"},
					},
				},
			},
		},

		// Playlist commands
		{
			Name:        "playlists",
			Description: "List all available playlists",
		},
		{
			Name:        "use",
			Description: "Load and play a saved playlist",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionString,
					Name:        "name",
					Description: "Playlist name to load",
					Required:    true,
				},
				{
					Type:        discordgo.ApplicationCommandOptionInteger,
					Name:        "start_index",
					Description: "Start playing from this song index (1-based)",
					Required:    false,
					MinValue:    func() *float64 { v := 1.0; return &v }(),
				},
			},
		},
		{
			Name:        "add",
			Description: "Quick add a song to the active playlist",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionString,
					Name:        "song",
					Description: "YouTube URL or search query",
					Required:    true,
				},
			},
		},
		{
			Name:        "remove",
			Description: "Remove a song from a playlist by index",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionString,
					Name:        "playlist",
					Description: "Playlist name",
					Required:    true,
				},
				{
					Type:        discordgo.ApplicationCommandOptionInteger,
					Name:        "index",
					Description: "Song index (1-based)",
					Required:    true,
					MinValue:    func() *float64 { v := 1.0; return &v }(),
				},
			},
		},
		{
			Name:        "playlist",
			Description: "Manage your playlists",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionSubCommand,
					Name:        "create",
					Description: "Create a new playlist",
					Options: []*discordgo.ApplicationCommandOption{
						{
							Type:        discordgo.ApplicationCommandOptionString,
							Name:        "name",
							Description: "Name for the new playlist",
							Required:    true,
						},
					},
				},
				{
					Type:        discordgo.ApplicationCommandOptionSubCommand,
					Name:        "delete",
					Description: "Delete an existing playlist",
					Options: []*discordgo.ApplicationCommandOption{
						{
							Type:        discordgo.ApplicationCommandOptionString,
							Name:        "name",
							Description: "Playlist name to delete",
							Required:    true,
						},
					},
				},
				{
					Type:        discordgo.ApplicationCommandOptionSubCommand,
					Name:        "show",
					Description: "Display playlist contents",
					Options: []*discordgo.ApplicationCommandOption{
						{
							Type:        discordgo.ApplicationCommandOptionString,
							Name:        "name",
							Description: "Playlist name to display",
							Required:    true,
						},
					},
				},
				{
					Type:        discordgo.ApplicationCommandOptionSubCommand,
					Name:        "add",
					Description: "Add a song to a playlist",
					Options: []*discordgo.ApplicationCommandOption{
						{
							Type:        discordgo.ApplicationCommandOptionString,
							Name:        "name",
							Description: "Playlist name",
							Required:    true,
						},
						{
							Type:        discordgo.ApplicationCommandOptionString,
							Name:        "song",
							Description: "YouTube URL or search query (leave empty for current song)",
							Required:    false,
						},
					},
				},
			},
		},

		// Utility commands
		{
			Name:        "join",
			Description: "Join your current voice channel",
		},
		{
			Name:        "leave",
			Description: "Leave voice channel and clear all state",
		},
		{
			Name:        "stats",
			Description: "Display bot statistics and status",
		},
		{
			Name:        "help",
			Description: "Show all available commands and usage",
		},
		{
			Name:        "sync",
			Description: "[Admin] Force synchronize slash commands with Discord",
		},
	}
}
