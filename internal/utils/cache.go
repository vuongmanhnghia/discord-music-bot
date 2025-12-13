package utils

import (
	"container/list"
	"sync"
	"time"
)

// CacheEntry represents an entry in the cache with TTL
type CacheEntry struct {
	Key        string
	Value      interface{}
	ExpiresAt  time.Time
	accessTime time.Time
}

// IsExpired returns true if the entry has expired
func (e *CacheEntry) IsExpired() bool {
	return !e.ExpiresAt.IsZero() && time.Now().After(e.ExpiresAt)
}

// SmartCache is an LRU cache with TTL support
type SmartCache struct {
	maxSize   int
	ttl       time.Duration
	items     map[string]*list.Element
	lruList   *list.List
	mu        sync.RWMutex
	hits      int64
	misses    int64
	evictions int64
}

// NewSmartCache creates a new cache with LRU eviction and TTL
func NewSmartCache(maxSize int, ttl time.Duration) *SmartCache {
	return &SmartCache{
		maxSize: maxSize,
		ttl:     ttl,
		items:   make(map[string]*list.Element),
		lruList: list.New(),
	}
}

// Get retrieves a value from the cache
func (c *SmartCache) Get(key string) (interface{}, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()

	elem, exists := c.items[key]
	if !exists {
		c.misses++
		return nil, false
	}

	entry := elem.Value.(*CacheEntry)

	// Check if expired
	if entry.IsExpired() {
		c.removeLocked(key)
		c.misses++
		return nil, false
	}

	// Update access time and move to front (most recently used)
	entry.accessTime = time.Now()
	c.lruList.MoveToFront(elem)
	c.hits++

	return entry.Value, true
}

// Set adds or updates a value in the cache
func (c *SmartCache) Set(key string, value interface{}) {
	c.mu.Lock()
	defer c.mu.Unlock()

	now := time.Now()
	expiresAt := time.Time{}
	if c.ttl > 0 {
		expiresAt = now.Add(c.ttl)
	}

	// Check if key already exists
	if elem, exists := c.items[key]; exists {
		entry := elem.Value.(*CacheEntry)
		entry.Value = value
		entry.ExpiresAt = expiresAt
		entry.accessTime = now
		c.lruList.MoveToFront(elem)
		return
	}

	// Create new entry
	entry := &CacheEntry{
		Key:        key,
		Value:      value,
		ExpiresAt:  expiresAt,
		accessTime: now,
	}

	// Add to front of LRU list
	elem := c.lruList.PushFront(entry)
	c.items[key] = elem

	// Evict if over capacity
	if c.lruList.Len() > c.maxSize {
		c.evictOldestLocked()
	}
}

// Delete removes a value from the cache
func (c *SmartCache) Delete(key string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.removeLocked(key)
}

// Clear removes all entries from the cache
func (c *SmartCache) Clear() {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.items = make(map[string]*list.Element)
	c.lruList.Init()
	c.hits = 0
	c.misses = 0
	c.evictions = 0
}

// Size returns the current number of entries
func (c *SmartCache) Size() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.lruList.Len()
}

// Stats returns cache statistics
func (c *SmartCache) Stats() (hits, misses, evictions int64, size int) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.hits, c.misses, c.evictions, c.lruList.Len()
}

// HitRate returns the cache hit rate (0.0 to 1.0)
func (c *SmartCache) HitRate() float64 {
	c.mu.RLock()
	defer c.mu.RUnlock()

	total := c.hits + c.misses
	if total == 0 {
		return 0.0
	}
	return float64(c.hits) / float64(total)
}

// CleanupExpired removes all expired entries
func (c *SmartCache) CleanupExpired() int {
	c.mu.Lock()
	defer c.mu.Unlock()

	removed := 0
	for key, elem := range c.items {
		entry := elem.Value.(*CacheEntry)
		if entry.IsExpired() {
			c.removeLocked(key)
			removed++
		}
	}
	return removed
}

// removeLocked removes an entry (must be called with lock held)
func (c *SmartCache) removeLocked(key string) {
	if elem, exists := c.items[key]; exists {
		c.lruList.Remove(elem)
		delete(c.items, key)
	}
}

// evictOldestLocked removes the least recently used entry (must be called with lock held)
func (c *SmartCache) evictOldestLocked() {
	elem := c.lruList.Back()
	if elem != nil {
		entry := elem.Value.(*CacheEntry)
		c.removeLocked(entry.Key)
		c.evictions++
	}
}

// StartCleanupWorker starts a background worker that periodically removes expired entries
func (c *SmartCache) StartCleanupWorker(interval time.Duration, stop <-chan struct{}) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			c.CleanupExpired()
		case <-stop:
			return
		}
	}
}
