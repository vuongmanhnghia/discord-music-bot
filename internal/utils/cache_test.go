package utils

import (
	"testing"
	"time"
)

func TestSmartCacheBasicOperations(t *testing.T) {
	cache := NewSmartCache(3, 0) // No TTL

	// Test Set and Get
	cache.Set("key1", "value1")
	val, ok := cache.Get("key1")
	if !ok {
		t.Error("Expected key1 to exist")
	}
	if val != "value1" {
		t.Errorf("Expected value1, got %v", val)
	}

	// Test Size
	cache.Set("key2", "value2")
	cache.Set("key3", "value3")
	if cache.Size() != 3 {
		t.Errorf("Expected size 3, got %d", cache.Size())
	}

	// Test Get non-existent key
	_, ok = cache.Get("nonexistent")
	if ok {
		t.Error("Expected key to not exist")
	}
}

func TestSmartCacheLRUEviction(t *testing.T) {
	cache := NewSmartCache(3, 0)

	// Fill cache
	cache.Set("key1", "value1")
	cache.Set("key2", "value2")
	cache.Set("key3", "value3")

	// Access key1 to make it most recently used
	cache.Get("key1")

	// Add new item - should evict key2 (least recently used)
	cache.Set("key4", "value4")

	if cache.Size() != 3 {
		t.Errorf("Expected size 3, got %d", cache.Size())
	}

	// key2 should be evicted
	_, ok := cache.Get("key2")
	if ok {
		t.Error("Expected key2 to be evicted")
	}

	// key1 should still exist
	_, ok = cache.Get("key1")
	if !ok {
		t.Error("Expected key1 to still exist")
	}
}

func TestSmartCacheTTL(t *testing.T) {
	cache := NewSmartCache(10, 50*time.Millisecond)

	cache.Set("key1", "value1")

	// Should exist immediately
	val, ok := cache.Get("key1")
	if !ok || val != "value1" {
		t.Error("Expected key1 to exist")
	}

	// Wait for expiration
	time.Sleep(100 * time.Millisecond)

	// Should be expired
	_, ok = cache.Get("key1")
	if ok {
		t.Error("Expected key1 to be expired")
	}
}

func TestSmartCacheUpdate(t *testing.T) {
	cache := NewSmartCache(10, 0)

	cache.Set("key1", "value1")
	cache.Set("key1", "value2") // Update

	val, ok := cache.Get("key1")
	if !ok || val != "value2" {
		t.Errorf("Expected value2, got %v", val)
	}

	if cache.Size() != 1 {
		t.Errorf("Expected size 1, got %d", cache.Size())
	}
}

func TestSmartCacheDelete(t *testing.T) {
	cache := NewSmartCache(10, 0)

	cache.Set("key1", "value1")
	cache.Delete("key1")

	_, ok := cache.Get("key1")
	if ok {
		t.Error("Expected key1 to be deleted")
	}

	if cache.Size() != 0 {
		t.Errorf("Expected size 0, got %d", cache.Size())
	}
}

func TestSmartCacheClear(t *testing.T) {
	cache := NewSmartCache(10, 0)

	cache.Set("key1", "value1")
	cache.Set("key2", "value2")
	cache.Set("key3", "value3")

	cache.Clear()

	if cache.Size() != 0 {
		t.Errorf("Expected size 0, got %d", cache.Size())
	}

	_, ok := cache.Get("key1")
	if ok {
		t.Error("Expected all keys to be cleared")
	}
}

func TestSmartCacheStats(t *testing.T) {
	cache := NewSmartCache(10, 0)

	cache.Set("key1", "value1")
	cache.Get("key1")     // hit
	cache.Get("key2")     // miss
	cache.Get("nonexist") // miss

	hits, misses, evictions, size := cache.Stats()

	if hits != 1 {
		t.Errorf("Expected 1 hit, got %d", hits)
	}
	if misses != 2 {
		t.Errorf("Expected 2 misses, got %d", misses)
	}
	if evictions != 0 {
		t.Errorf("Expected 0 evictions, got %d", evictions)
	}
	if size != 1 {
		t.Errorf("Expected size 1, got %d", size)
	}
}

func TestSmartCacheHitRate(t *testing.T) {
	cache := NewSmartCache(10, 0)

	// Empty cache should have 0.0 hit rate
	if rate := cache.HitRate(); rate != 0.0 {
		t.Errorf("Expected hit rate 0.0, got %f", rate)
	}

	cache.Set("key1", "value1")
	cache.Get("key1") // hit
	cache.Get("key2") // miss

	rate := cache.HitRate()
	expected := 0.5
	if rate != expected {
		t.Errorf("Expected hit rate %f, got %f", expected, rate)
	}
}

func TestSmartCacheCleanupExpired(t *testing.T) {
	cache := NewSmartCache(10, 50*time.Millisecond)

	cache.Set("key1", "value1")
	cache.Set("key2", "value2")
	cache.Set("key3", "value3")

	// Wait for expiration
	time.Sleep(100 * time.Millisecond)

	removed := cache.CleanupExpired()
	if removed != 3 {
		t.Errorf("Expected 3 expired entries, got %d", removed)
	}

	if cache.Size() != 0 {
		t.Errorf("Expected size 0 after cleanup, got %d", cache.Size())
	}
}

func TestSmartCacheConcurrency(t *testing.T) {
	cache := NewSmartCache(100, 0)
	done := make(chan bool)

	// Concurrent writes
	for i := 0; i < 10; i++ {
		go func(id int) {
			for j := 0; j < 100; j++ {
				cache.Set(string(rune(id*100+j)), id)
			}
			done <- true
		}(i)
	}

	// Concurrent reads
	for i := 0; i < 10; i++ {
		go func(id int) {
			for j := 0; j < 100; j++ {
				cache.Get(string(rune(id*100 + j)))
			}
			done <- true
		}(i)
	}

	// Wait for all goroutines
	for i := 0; i < 20; i++ {
		<-done
	}

	// Should not panic and maintain max size
	if cache.Size() > 100 {
		t.Errorf("Cache exceeded max size: %d", cache.Size())
	}
}

func TestSmartCacheEvictionStats(t *testing.T) {
	cache := NewSmartCache(3, 0)

	cache.Set("key1", "value1")
	cache.Set("key2", "value2")
	cache.Set("key3", "value3")
	cache.Set("key4", "value4") // Should evict key1

	_, _, evictions, _ := cache.Stats()
	if evictions != 1 {
		t.Errorf("Expected 1 eviction, got %d", evictions)
	}
}
