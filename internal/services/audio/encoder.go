package audio

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"os/exec"
	"time"

	"github.com/jonas747/ogg"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

var (
	// ErrEncodingFailed is returned when encoding fails
	ErrEncodingFailed = errors.New("audio encoding failed")
	// ErrAlreadyPlaying is returned when already playing
	ErrAlreadyPlaying = errors.New("already playing")
)

// AudioEncoder handles encoding audio streams for Discord
type AudioEncoder struct {
	logger *logger.Logger
}

// NewAudioEncoder creates a new audio encoder
func NewAudioEncoder(log *logger.Logger) *AudioEncoder {
	return &AudioEncoder{
		logger: log,
	}
}

// EncodeOptions contains options for encoding
type EncodeOptions struct {
	Volume      int    // 0-100, default 100
	Bitrate     int    // in kbps, default 128
	Application string // audio, voip, or lowdelay
	BufferSize  int    // buffer size in samples
}

// DefaultEncodeOptions returns default encoding options
func DefaultEncodeOptions() *EncodeOptions {
	return &EncodeOptions{
		Volume:      100,
		Bitrate:     128,
		Application: "audio",
		BufferSize:  1024, // Larger buffer for smoother playback (~20 seconds of audio)
	}
}

// EncodeStream encodes an audio stream URL for Discord playback
// Returns a channel that provides encoded audio frames
func (e *AudioEncoder) EncodeStream(streamURL string, options *EncodeOptions) (<-chan []byte, <-chan error, error) {
	if options == nil {
		options = DefaultEncodeOptions()
	}

	e.logger.WithField("url", streamURL).Info("Starting audio encoding...")

	frameChannel := make(chan []byte, options.BufferSize)
	errorChannel := make(chan error, 1)

	// Start encoding in goroutine - use yt-dlp pipe approach to bypass 403 errors
	go e.encodeWithYtDlpPipe(streamURL, options, frameChannel, errorChannel)

	return frameChannel, errorChannel, nil
}

// encodeWithYtDlpPipe uses yt-dlp piped to FFmpeg to encode audio
// This bypasses YouTube's 403 restrictions that occur when FFmpeg accesses URLs directly
func (e *AudioEncoder) encodeWithYtDlpPipe(streamURL string, options *EncodeOptions, frameChannel chan []byte, errorChannel chan error) {
	defer close(frameChannel)
	defer close(errorChannel)

	e.logger.WithField("url", streamURL[:min(80, len(streamURL))]).Info("📻 Starting yt-dlp -> FFmpeg piped encoding...")

	// Build yt-dlp | FFmpeg pipeline
	// yt-dlp downloads and outputs to stdout, FFmpeg reads from stdin and outputs Opus to stdout

	// Start yt-dlp process to download audio to stdout
	ytDlpArgs := []string{
		"-f", "bestaudio/best",
		"-o", "-", // Output to stdout
		"--no-playlist",
		"--no-check-certificate",
		"--geo-bypass",
		"--quiet",
		"--no-warnings",
		streamURL,
	}

	ytDlpCmd := exec.Command("yt-dlp", ytDlpArgs...)
	ytDlpStdout, err := ytDlpCmd.StdoutPipe()
	if err != nil {
		e.logger.WithError(err).Error("❌ Failed to get yt-dlp stdout pipe")
		errorChannel <- fmt.Errorf("failed to get yt-dlp stdout: %w", err)
		return
	}
	ytDlpStderr, err := ytDlpCmd.StderrPipe()
	if err != nil {
		e.logger.WithError(err).Error("❌ Failed to get yt-dlp stderr pipe")
		errorChannel <- fmt.Errorf("failed to get yt-dlp stderr: %w", err)
		return
	}

	// Log yt-dlp errors in background
	go func() {
		scanner := bufio.NewScanner(ytDlpStderr)
		for scanner.Scan() {
			e.logger.WithField("yt-dlp", scanner.Text()).Debug("yt-dlp output")
		}
	}()

	// Start FFmpeg process to encode to OGG/Opus
	// FFmpeg reads from stdin (pipe from yt-dlp) and outputs to stdout
	// Using similar args to TwiN/discord-music-bot
	ffmpegArgs := []string{
		"-i", "pipe:0", // Read from stdin
		"-reconnect", "1",
		"-reconnect_at_eof", "1",
		"-reconnect_streamed", "1",
		"-reconnect_delay_max", "2",
		"-map", "0:a",
		"-acodec", "libopus",
		"-f", "ogg",
		"-compression_level", "5",
		"-ar", "48000",
		"-ac", "2",
		"-b:a", fmt.Sprintf("%d", options.Bitrate*1000),
		"-application", options.Application,
		"-frame_duration", "20",
		"-loglevel", "error",
		"pipe:1", // Output to stdout
	}

	ffmpegCmd := exec.Command("ffmpeg", ffmpegArgs...)
	ffmpegCmd.Stdin = ytDlpStdout // Connect yt-dlp stdout to FFmpeg stdin

	ffmpegStdout, err := ffmpegCmd.StdoutPipe()
	if err != nil {
		e.logger.WithError(err).Error("❌ Failed to get FFmpeg stdout pipe")
		errorChannel <- fmt.Errorf("failed to get ffmpeg stdout: %w", err)
		return
	}
	ffmpegStderr, err := ffmpegCmd.StderrPipe()
	if err != nil {
		e.logger.WithError(err).Error("❌ Failed to get FFmpeg stderr pipe")
		errorChannel <- fmt.Errorf("failed to get ffmpeg stderr: %w", err)
		return
	}

	// Log FFmpeg errors in background
	go func() {
		scanner := bufio.NewScanner(ffmpegStderr)
		for scanner.Scan() {
			e.logger.WithField("ffmpeg", scanner.Text()).Warn("FFmpeg output")
		}
	}()

	// Start both processes
	if err := ytDlpCmd.Start(); err != nil {
		e.logger.WithError(err).Error("❌ Failed to start yt-dlp")
		errorChannel <- fmt.Errorf("failed to start yt-dlp: %w", err)
		return
	}

	if err := ffmpegCmd.Start(); err != nil {
		ytDlpCmd.Process.Kill()
		e.logger.WithError(err).Error("❌ Failed to start FFmpeg")
		errorChannel <- fmt.Errorf("failed to start ffmpeg: %w", err)
		return
	}

	// Ensure processes are killed on exit
	defer func() {
		if ytDlpCmd.Process != nil {
			ytDlpCmd.Process.Kill()
			ytDlpCmd.Wait()
		}
		if ffmpegCmd.Process != nil {
			ffmpegCmd.Process.Kill()
			ffmpegCmd.Wait()
		}
	}()

	e.logger.Info("✅ yt-dlp -> FFmpeg pipeline started, reading Opus frames from OGG stream...")

	// Use PacketDecoder (from TwiN/discord-music-bot approach) for cleaner packet reading
	decoder := ogg.NewPacketDecoder(ogg.NewDecoder(ffmpegStdout))

	frameCount := 0
	lastLogTime := time.Now()

	// Rate limiting: Opus frames are 20ms each, so 50 frames/second
	// We need to throttle encoding to match playback rate
	frameInterval := 20 * time.Millisecond
	startTime := time.Now()

	// Skip first 2 packets (Opus header and comment metadata)
	skipPackets := 2

	for {
		// Decode next packet
		packet, _, err := decoder.Decode()
		if err != nil {
			if err == io.EOF {
				e.logger.WithField("frames", frameCount).Info("✅ Encoding completed (EOF)")
				return
			}
			if frameCount > 0 {
				e.logger.WithError(err).WithField("frames", frameCount).Warn("⚠️ Encoding ended after frames")
				return
			}
			e.logger.WithError(err).Error("❌ Error decoding OGG packet")
			errorChannel <- err
			return
		}

		// Skip metadata packets
		if skipPackets > 0 {
			skipPackets--
			continue
		}

		// Send Opus frame
		if len(packet) > 0 {
			frameCount++

			// Log progress every 5 seconds
			if time.Since(lastLogTime) > 5*time.Second {
				e.logger.WithField("frames", frameCount).Debug("Encoding in progress...")
				lastLogTime = time.Now()
			}

			// Rate limiting: wait until it's time to send this frame
			// This prevents buffer overflow by matching encode rate to playback rate
			expectedTime := startTime.Add(time.Duration(frameCount) * frameInterval)
			now := time.Now()
			if now.Before(expectedTime) {
				time.Sleep(expectedTime.Sub(now))
			}

			// Send frame to channel (blocking)
			frameChannel <- packet
		}
	}
}
