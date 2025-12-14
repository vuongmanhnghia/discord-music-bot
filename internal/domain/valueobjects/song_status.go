package valueobjects

// SongStatus represents the processing status of a song
type SongStatus string

const (
	SongStatusPending    SongStatus = "pending"
	SongStatusProcessing SongStatus = "processing"
	SongStatusReady      SongStatus = "ready"
	SongStatusFailed     SongStatus = "failed"
)

// String returns the string representation
func (s SongStatus) String() string {
	return string(s)
}

// IsValid checks if the status is valid
func (s SongStatus) IsValid() bool {
	switch s {
	case SongStatusPending, SongStatusProcessing, SongStatusReady, SongStatusFailed:
		return true
	}
	return false
}
