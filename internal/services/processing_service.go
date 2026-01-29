package services

import (
	"context"
	"errors"
	"strings"
	"sync"

	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/youtube"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

var (
	// ErrProcessingServiceStopped is returned when the service is stopped
	ErrProcessingServiceStopped = errors.New("processing service stopped")
	// ErrMaxQueueSize is returned when queue is full
	ErrMaxQueueSize = errors.New("processing queue is full")
)

// ProcessingTask represents a song processing task
type ProcessingTask struct {
	Song     *entities.Song
	Priority int // Higher = more urgent
}

// ProcessingService handles async song processing with worker pool
type ProcessingService struct {
	ytService  *youtube.Service
	logger     *logger.Logger
	queue      chan *ProcessingTask
	workers    int
	wg         sync.WaitGroup
	ctx        context.Context
	cancel     context.CancelFunc
	mu         sync.RWMutex
	processing map[string]bool // Track songs being processed
	stats      ProcessingStats
}

// ProcessingStats tracks processing statistics
type ProcessingStats struct {
	Processed int64
	Failed    int64
	Pending   int64
}

// NewProcessingService creates a new processing service
func NewProcessingService(ytService *youtube.Service, workers int, queueSize int, log *logger.Logger) *ProcessingService {
	ctx, cancel := context.WithCancel(context.Background())

	return &ProcessingService{
		ytService:  ytService,
		logger:     log,
		queue:      make(chan *ProcessingTask, queueSize),
		workers:    workers,
		ctx:        ctx,
		cancel:     cancel,
		processing: make(map[string]bool),
	}
}

// Start starts the worker pool
func (s *ProcessingService) Start() {
	s.logger.WithField("workers", s.workers).Info("Starting processing service...")

	for i := 0; i < s.workers; i++ {
		s.wg.Add(1)
		go s.worker(i)
	}

	s.logger.Info("✅ Processing service started")
}

// Stop stops the worker pool gracefully
func (s *ProcessingService) Stop() {
	s.logger.Info("Stopping processing service...")
	s.cancel()
	close(s.queue)
	s.wg.Wait()
	s.logger.Info("✅ Processing service stopped")
}

// Submit submits a song for processing
func (s *ProcessingService) Submit(song *entities.Song, priority int) error {
	// Check if already processing
	s.mu.Lock()
	if s.processing[song.ID] {
		s.mu.Unlock()
		s.logger.WithField("song_id", song.ID).Debug("Song already being processed")
		return nil
	}
	s.processing[song.ID] = true
	s.mu.Unlock()

	task := &ProcessingTask{
		Song:     song,
		Priority: priority,
	}

	select {
	case s.queue <- task:
		s.mu.Lock()
		s.stats.Pending++
		s.mu.Unlock()
		s.logger.WithFields(map[string]interface{}{
			"song_id":  song.ID,
			"priority": priority,
		}).Debug("Song submitted for processing")
		return nil
	case <-s.ctx.Done():
		s.mu.Lock()
		delete(s.processing, song.ID)
		s.mu.Unlock()
		return ErrProcessingServiceStopped
	default:
		s.mu.Lock()
		delete(s.processing, song.ID)
		s.mu.Unlock()
		s.logger.WithFields(map[string]interface{}{
			"song_id":    song.ID,
			"queue_size": len(s.queue),
			"max_size":   cap(s.queue),
		}).Warn("Processing queue is full, rejecting song")
		return ErrMaxQueueSize
	}
}

// worker processes tasks from the queue
func (s *ProcessingService) worker(id int) {
	defer s.wg.Done()

	s.logger.WithField("worker_id", id).Debug("Worker started")

	for {
		select {
		case task, ok := <-s.queue:
			if !ok {
				s.logger.WithField("worker_id", id).Debug("Worker stopping - queue closed")
				return
			}

			s.processTask(task, id)

		case <-s.ctx.Done():
			s.logger.WithField("worker_id", id).Debug("Worker stopping - context cancelled")
			return
		}
	}
}

// processTask processes a single task
func (s *ProcessingService) processTask(task *ProcessingTask, workerID int) {
	song := task.Song
	songID := song.ID

	defer func() {
		s.mu.Lock()
		delete(s.processing, songID)
		s.stats.Pending--
		s.mu.Unlock()
	}()

	s.logger.WithFields(map[string]interface{}{
		"worker_id": workerID,
		"song_id":   songID,
		"source":    song.SourceType,
	}).Info("Processing song...")

	// Mark as processing
	song.MarkProcessing()

	// Process based on source type
	var err error
	switch song.SourceType {
	case valueobjects.SourceTypeYouTube:
		err = s.processYouTubeSong(song)
	case valueobjects.SourceTypeURL:
		err = s.processURLSong(song)
	default:
		err = errors.New("unsupported source type")
	}

	if err != nil {
		s.logger.WithError(err).WithField("song_id", songID).Error("Processing failed")
		song.MarkFailed(err.Error())
		s.updateStats(false)
		return
	}

	s.logger.WithField("song_id", songID).Info("✅ Song processed successfully")
	s.updateStats(true)
}

// processYouTubeSong processes a YouTube song or web URL (including SoundCloud)
func (s *ProcessingService) processYouTubeSong(song *entities.Song) error {
	source := song.OriginalInput

	// Check if it's a web URL (YouTube, SoundCloud, or other yt-dlp supported sites)
	if strings.HasPrefix(source, "http://") || strings.HasPrefix(source, "https://") {
		// Extract info from URL using yt-dlp
		info, err := s.ytService.ExtractInfo(source)
		if err != nil {
			return err
		}

		// Get stream URL - use original source URL for non-YouTube platforms
		// For YouTube, info.ID is the video ID; for SoundCloud/others, use the full URL
		var identifier string
		if youtube.IsYouTubeURL(source) {
			identifier = info.ID // YouTube video ID
		} else {
			identifier = source // Full URL for SoundCloud, etc.
		}

		streamURL, err := s.ytService.GetStreamURL(identifier)
		if err != nil {
			return err
		}

		// Mark as ready with metadata
		song.MarkReady(info.ToSongMetadata(), streamURL)
		return nil
	}

	// Search query (search on YouTube)
	results, err := s.ytService.Search(source, 1)
	if err != nil {
		return err
	}

	if len(results) == 0 {
		return errors.New("no search results found")
	}

	info := &results[0]
	streamURL, err := s.ytService.GetStreamURL(info.ID)
	if err != nil {
		return err
	}

	song.MarkReady(info.ToSongMetadata(), streamURL)
	return nil
}

// processFileSong processes a local file song
func (s *ProcessingService) processFileSong(song *entities.Song) error {
	// For local files, the source is already the stream URL
	// Create basic metadata
	metadata := &valueobjects.SongMetadata{
		Title:    song.OriginalInput,
		Duration: 0, // Unknown duration for files
	}
	song.MarkReady(metadata, song.OriginalInput)
	return nil
}

// processURLSong processes a direct URL song
func (s *ProcessingService) processURLSong(song *entities.Song) error {
	// For direct URLs, use as-is
	metadata := &valueobjects.SongMetadata{
		Title:    song.OriginalInput,
		Duration: 0,
	}
	song.MarkReady(metadata, song.OriginalInput)
	return nil
}

// updateStats updates processing statistics
func (s *ProcessingService) updateStats(success bool) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if success {
		s.stats.Processed++
	} else {
		s.stats.Failed++
	}
}

// GetStats returns processing statistics
func (s *ProcessingService) GetStats() ProcessingStats {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.stats
}

// QueueSize returns current queue size
func (s *ProcessingService) QueueSize() int {
	return len(s.queue)
}

// IsProcessing checks if a song is currently being processed
func (s *ProcessingService) IsProcessing(songID string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.processing[songID]
}
