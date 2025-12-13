package logger

import (
	"io"
	"os"

	"github.com/sirupsen/logrus"
)

// Logger wraps logrus for structured logging
type Logger struct {
	*logrus.Logger
}

// Config for logger initialization
type Config struct {
	Level  string // debug, info, warn, error
	Format string // text or json
	Output io.Writer
}

// New creates a new logger instance
func New(cfg Config) *Logger {
	log := logrus.New()

	// Set level
	level, err := logrus.ParseLevel(cfg.Level)
	if err != nil {
		level = logrus.InfoLevel
	}
	log.SetLevel(level)

	// Set formatter
	if cfg.Format == "json" {
		log.SetFormatter(&logrus.JSONFormatter{
			TimestampFormat: "2006-01-02 15:04:05",
		})
	} else {
		log.SetFormatter(&logrus.TextFormatter{
			FullTimestamp:   true,
			TimestampFormat: "2006-01-02 15:04:05",
			ForceColors:     true,
		})
	}

	// Set output
	if cfg.Output != nil {
		log.SetOutput(cfg.Output)
	} else {
		log.SetOutput(os.Stdout)
	}

	return &Logger{Logger: log}
}

// WithField adds a single field to the log entry
func (l *Logger) WithField(key string, value interface{}) *logrus.Entry {
	return l.Logger.WithField(key, value)
}

// WithFields adds multiple fields to the log entry
func (l *Logger) WithFields(fields logrus.Fields) *logrus.Entry {
	return l.Logger.WithFields(fields)
}

// WithError adds an error field to the log entry
func (l *Logger) WithError(err error) *logrus.Entry {
	return l.Logger.WithError(err)
}
