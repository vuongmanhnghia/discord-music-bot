package commands

import (
	"github.com/bwmarrin/discordgo"
)

// Colors for embeds
const (
	ColorPrimary = 0x5865F2 // Discord Blurple
	ColorSuccess = 0x57F287 // Green
	ColorWarning = 0xFEE75C // Yellow
	ColorError   = 0xED4245 // Red
	ColorInfo    = 0x3498DB // Blue
)

// respond sends a simple text response
func respond(s *discordgo.Session, i *discordgo.InteractionCreate, message string) error {
	return s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseChannelMessageWithSource,
		Data: &discordgo.InteractionResponseData{
			Content: message,
		},
	})
}

// respondEmbed sends an embed response
func respondEmbed(s *discordgo.Session, i *discordgo.InteractionCreate, embed *discordgo.MessageEmbed) error {
	return s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseChannelMessageWithSource,
		Data: &discordgo.InteractionResponseData{
			Embeds: []*discordgo.MessageEmbed{embed},
		},
	})
}

// respondError sends an error response with red embed
func respondError(s *discordgo.Session, i *discordgo.InteractionCreate, message string) error {
	embed := &discordgo.MessageEmbed{
		Description: "❌ " + message,
		Color:       ColorError,
	}
	return respondEmbed(s, i, embed)
}

// respondSuccess sends a success response with green embed
func respondSuccess(s *discordgo.Session, i *discordgo.InteractionCreate, message string) error {
	embed := &discordgo.MessageEmbed{
		Description: "✅ " + message,
		Color:       ColorSuccess,
	}
	return respondEmbed(s, i, embed)
}

// respondInfo sends an info response with blue embed
func respondInfo(s *discordgo.Session, i *discordgo.InteractionCreate, message string) error {
	embed := &discordgo.MessageEmbed{
		Description: message,
		Color:       ColorInfo,
	}
	return respondEmbed(s, i, embed)
}

// deferResponse defers the response for long operations
func deferResponse(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	return s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseDeferredChannelMessageWithSource,
	})
}

// deferEphemeral defers with ephemeral flag
func deferEphemeral(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	return s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseDeferredChannelMessageWithSource,
		Data: &discordgo.InteractionResponseData{
			Flags: discordgo.MessageFlagsEphemeral,
		},
	})
}

// followUp sends a follow-up message
func followUp(s *discordgo.Session, i *discordgo.InteractionCreate, message string) error {
	_, err := s.FollowupMessageCreate(i.Interaction, false, &discordgo.WebhookParams{
		Content: message,
	})
	return err
}

// followUpEmbed sends a follow-up embed message
func followUpEmbed(s *discordgo.Session, i *discordgo.InteractionCreate, embed *discordgo.MessageEmbed) error {
	_, err := s.FollowupMessageCreate(i.Interaction, false, &discordgo.WebhookParams{
		Embeds: []*discordgo.MessageEmbed{embed},
	})
	return err
}

// followUpError sends an error follow-up message
func followUpError(s *discordgo.Session, i *discordgo.InteractionCreate, message string) error {
	embed := &discordgo.MessageEmbed{
		Description: "❌ " + message,
		Color:       ColorError,
	}
	return followUpEmbed(s, i, embed)
}

// followUpSuccess sends a success follow-up message
func followUpSuccess(s *discordgo.Session, i *discordgo.InteractionCreate, message string) error {
	embed := &discordgo.MessageEmbed{
		Description: "✅ " + message,
		Color:       ColorSuccess,
	}
	return followUpEmbed(s, i, embed)
}

// EmbedBuilder helps build consistent embeds
type EmbedBuilder struct {
	embed *discordgo.MessageEmbed
}

// NewEmbed creates a new embed builder
func NewEmbed() *EmbedBuilder {
	return &EmbedBuilder{
		embed: &discordgo.MessageEmbed{
			Color: ColorPrimary,
		},
	}
}

// Title sets the embed title
func (b *EmbedBuilder) Title(title string) *EmbedBuilder {
	b.embed.Title = title
	return b
}

// Description sets the embed description
func (b *EmbedBuilder) Description(desc string) *EmbedBuilder {
	b.embed.Description = desc
	return b
}

// Color sets the embed color
func (b *EmbedBuilder) Color(color int) *EmbedBuilder {
	b.embed.Color = color
	return b
}

// Field adds a field to the embed
func (b *EmbedBuilder) Field(name, value string, inline bool) *EmbedBuilder {
	b.embed.Fields = append(b.embed.Fields, &discordgo.MessageEmbedField{
		Name:   name,
		Value:  value,
		Inline: inline,
	})
	return b
}

// Thumbnail sets the thumbnail URL
func (b *EmbedBuilder) Thumbnail(url string) *EmbedBuilder {
	if url != "" {
		b.embed.Thumbnail = &discordgo.MessageEmbedThumbnail{URL: url}
	}
	return b
}

// Footer sets the footer text
func (b *EmbedBuilder) Footer(text string) *EmbedBuilder {
	b.embed.Footer = &discordgo.MessageEmbedFooter{Text: text}
	return b
}

// FooterIcon sets footer with icon
func (b *EmbedBuilder) FooterIcon(text, iconURL string) *EmbedBuilder {
	b.embed.Footer = &discordgo.MessageEmbedFooter{
		Text:    text,
		IconURL: iconURL,
	}
	return b
}

// Author sets the author
func (b *EmbedBuilder) Author(name, iconURL, url string) *EmbedBuilder {
	b.embed.Author = &discordgo.MessageEmbedAuthor{
		Name:    name,
		IconURL: iconURL,
		URL:     url,
	}
	return b
}

// Timestamp sets the timestamp
func (b *EmbedBuilder) Timestamp(ts string) *EmbedBuilder {
	b.embed.Timestamp = ts
	return b
}

// Build returns the built embed
func (b *EmbedBuilder) Build() *discordgo.MessageEmbed {
	return b.embed
}
