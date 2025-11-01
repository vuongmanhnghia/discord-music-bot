# Tests for Discord Music Bot

This directory contains comprehensive tests for the Discord Music Bot.

## Structure

```
tests/
├── unit/               # Unit tests for individual components
│   ├── test_song_entity.py
│   ├── test_tracklist.py
│   └── ...
├── integration/        # Integration tests for component interactions
├── fixtures/          # Shared test data and fixtures
├── conftest.py        # Pytest configuration and shared fixtures
└── README.md          # This file
```

## Running Tests

### Install Development Dependencies

```bash
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run slow tests
pytest -m slow

# Run tests that don't require network
pytest -m "not network"
```

### Run Specific Test Files

```bash
# Run song entity tests
pytest tests/unit/test_song_entity.py

# Run tracklist tests
pytest tests/unit/test_tracklist.py
```

### Run with Coverage

```bash
# Generate coverage report
pytest --cov=bot --cov-report=html

# View coverage report
# Open coverage_html/index.html in browser
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Specific Test

```bash
pytest tests/unit/test_song_entity.py::TestSongCreation::test_create_song_minimal
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.network` - Tests requiring network access

## Writing Tests

### Unit Test Example

```python
import pytest
from bot.domain.entities.song import Song
from bot.domain.valueobjects.source_type import SourceType

class TestSongCreation:
    def test_create_song(self):
        song = Song(
            original_input="test",
            source_type=SourceType.YOUTUBE
        )
        assert song.original_input == "test"
```

### Async Test Example

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

### Using Fixtures

```python
def test_with_fixture(mock_song):
    """Uses mock_song fixture from conftest.py"""
    assert mock_song.status == SongStatus.PENDING
```

## Continuous Integration

Tests are automatically run on:
- Pull requests
- Commits to main branch
- Before deployment

## Code Coverage Goals

- Overall coverage: > 80%
- Domain entities: > 90%
- Critical services: > 85%

## Best Practices

1. **Test Isolation** - Each test should be independent
2. **Clear Names** - Test names should describe what they test
3. **Arrange-Act-Assert** - Follow AAA pattern
4. **Mock External Dependencies** - Don't hit real APIs in tests
5. **Fast Tests** - Keep unit tests fast (< 1 second each)

## Troubleshooting

### Import Errors

Make sure you're running tests from the project root:

```bash
cd /home/nagih/Workspaces/noob/bot/discord-music-bot
pytest
```

### Async Errors

Ensure you're using `@pytest.mark.asyncio` for async tests.

### Missing Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```
