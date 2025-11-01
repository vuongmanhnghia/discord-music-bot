# Contributing to Discord Music Bot

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Quality](#code-quality)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Code Style](#code-style)

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/discord-music-bot.git`
3. Create a new branch: `git checkout -b feature/your-feature-name`

## Development Setup

### Prerequisites

- Python 3.10 or higher
- FFmpeg
- Git

### Install Dependencies

```bash
# Install runtime dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### Environment Setup

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your BOT_TOKEN
nano .env
```

## Code Quality

We use several tools to maintain code quality:

### Pre-commit Hooks

Pre-commit hooks run automatically before each commit:

```bash
# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Update hooks to latest versions
pre-commit autoupdate
```

### Code Formatting

We use **Black** for code formatting:

```bash
# Format all Python files
black bot/ tests/

# Check formatting without changes
black --check bot/ tests/
```

### Linting

We use **Ruff** for fast Python linting:

```bash
# Run linter
ruff check bot/ tests/

# Auto-fix issues
ruff check --fix bot/ tests/
```

### Type Checking

We use **mypy** for static type checking:

```bash
# Run type checker
mypy bot/ --config-file mypy.ini
```

### Import Sorting

We use **isort** for consistent import ordering:

```bash
# Sort imports
isort bot/ tests/

# Check without changes
isort --check bot/ tests/
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=bot --cov-report=html

# Run specific test file
pytest tests/unit/test_song_entity.py

# Run specific test
pytest tests/unit/test_song_entity.py::TestSongCreation::test_create_song_minimal

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Writing Tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Use descriptive test names: `test_<what>_<when>_<expected>`
- Follow the Arrange-Act-Assert pattern
- Use pytest fixtures from `conftest.py`

Example:

```python
import pytest

@pytest.mark.unit
def test_song_creation_with_valid_input(mock_song):
    """Test that song is created successfully with valid input"""
    # Arrange - done by fixture

    # Act
    song = mock_song

    # Assert
    assert song.original_input is not None
    assert song.status == SongStatus.PENDING
```

## Submitting Changes

### Commit Message Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**

```
feat(playback): add playlist shuffle functionality

Implement shuffle mode for playlists with proper randomization
and state management.

Closes #123
```

```
fix(audio): resolve memory leak in audio player

Fixed issue where FFmpeg processes were not properly terminated,
causing memory accumulation over time.

Fixes #456
```

### Pull Request Process

1. **Update your branch**:
   ```bash
   git checkout main
   git pull origin main
   git checkout your-feature-branch
   git rebase main
   ```

2. **Run all checks**:
   ```bash
   # Run tests
   pytest

   # Run linting
   ruff check bot/ tests/

   # Run type checking
   mypy bot/

   # Run formatting
   black --check bot/ tests/
   ```

3. **Push your changes**:
   ```bash
   git push origin your-feature-branch
   ```

4. **Create Pull Request**:
   - Go to GitHub and create a pull request
   - Fill in the PR template
   - Link related issues
   - Request review

5. **Address review feedback**:
   - Make requested changes
   - Push additional commits
   - Re-request review when ready

## Code Style

### Python Style Guide

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use Black for formatting (120 characters line length)
- Use type hints for all function signatures
- Write docstrings for all public functions and classes
- Keep functions small and focused (Single Responsibility)

### Naming Conventions

- **Classes**: PascalCase (`SongEntity`, `PlaybackService`)
- **Functions/Methods**: snake_case (`process_song`, `get_metadata`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_QUEUE_SIZE`, `DEFAULT_VOLUME`)
- **Private methods**: prefix with underscore (`_internal_method`)

### Documentation

- Use Google-style docstrings
- Include examples for complex functionality
- Document parameters, return values, and exceptions

Example:

```python
def process_song(song: Song, priority: int = 0) -> bool:
    """
    Process a song for playback.

    Args:
        song: The song entity to process
        priority: Processing priority (0=normal, 1=high)

    Returns:
        True if processing succeeded, False otherwise

    Raises:
        SongProcessingError: If song processing fails

    Example:
        >>> song = Song(original_input="https://youtube.com/...")
        >>> success = process_song(song, priority=1)
        >>> assert success
    """
    pass
```

### Error Handling

- Use custom exceptions from `bot.utils.exceptions`
- Log errors appropriately
- Provide helpful error messages
- Don't silently catch exceptions

```python
from bot.utils.exceptions import SongProcessingError

try:
    result = process_song(song)
except SongProcessingError as e:
    logger.error(f"Failed to process {song.display_name}: {e}")
    raise
```

## Project Structure

```
discord-music-bot/
├── bot/                    # Main application code
│   ├── commands/          # Discord slash commands
│   ├── config/            # Configuration
│   ├── domain/            # Domain entities and value objects
│   ├── services/          # Business logic
│   ├── utils/             # Utilities and helpers
│   └── music_bot.py       # Main bot class
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── conftest.py       # Test fixtures
├── .github/              # GitHub Actions workflows
└── docs/                 # Documentation
```

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for questions
- Check existing issues and discussions first

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
