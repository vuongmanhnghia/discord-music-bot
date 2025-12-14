package database

import (
	"context"
	"database/sql"
	"embed"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jackc/pgx/v5/stdlib"
	"github.com/pressly/goose/v3"
	"github.com/sirupsen/logrus"
)

//go:embed migrations/*.sql
var embedMigrations embed.FS

// DB wraps pgxpool.Pool and provides query methods
type DB struct {
	Pool    *pgxpool.Pool
	Queries *Queries
	sqlDB   *sql.DB // For goose migrations
}

// Config holds database configuration
type Config struct {
	DatabaseURL     string
	MaxConns        int32
	MinConns        int32
	MaxConnLifetime time.Duration
	MaxConnIdleTime time.Duration
}

// DefaultConfig returns default database configuration
func DefaultConfig(databaseURL string) *Config {
	return &Config{
		DatabaseURL:     databaseURL,
		MaxConns:        10,
		MinConns:        2,
		MaxConnLifetime: time.Hour,
		MaxConnIdleTime: 30 * time.Minute,
	}
}

// Connect creates a new database connection pool
func Connect(ctx context.Context, cfg *Config) (*DB, error) {
	poolConfig, err := pgxpool.ParseConfig(cfg.DatabaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse database URL: %w", err)
	}

	// Configure pool settings
	poolConfig.MaxConns = cfg.MaxConns
	poolConfig.MinConns = cfg.MinConns
	poolConfig.MaxConnLifetime = cfg.MaxConnLifetime
	poolConfig.MaxConnIdleTime = cfg.MaxConnIdleTime

	// Create connection pool
	pool, err := pgxpool.NewWithConfig(ctx, poolConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create connection pool: %w", err)
	}

	// Test connection
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	// Create stdlib wrapper for goose migrations
	sqlDB := stdlib.OpenDBFromPool(pool)

	db := &DB{
		Pool:    pool,
		Queries: New(pool),
		sqlDB:   sqlDB,
	}

	logrus.Info("✅ Database connection established")
	return db, nil
}

// Close closes the database connection pool
func (db *DB) Close() {
	if db.sqlDB != nil {
		db.sqlDB.Close()
	}
	if db.Pool != nil {
		db.Pool.Close()
		logrus.Info("Database connection closed")
	}
}

// RunMigrations runs all pending database migrations
func (db *DB) RunMigrations(ctx context.Context) error {
	// Set up goose with embedded migrations
	goose.SetBaseFS(embedMigrations)

	if err := goose.SetDialect("postgres"); err != nil {
		return fmt.Errorf("failed to set goose dialect: %w", err)
	}

	if err := goose.UpContext(ctx, db.sqlDB, "migrations"); err != nil {
		return fmt.Errorf("failed to run migrations: %w", err)
	}

	logrus.Info("✅ Database migrations completed")
	return nil
}

// Health checks if the database is healthy
func (db *DB) Health(ctx context.Context) error {
	return db.Pool.Ping(ctx)
}

// Stats returns database connection pool statistics
func (db *DB) Stats() *pgxpool.Stat {
	return db.Pool.Stat()
}
