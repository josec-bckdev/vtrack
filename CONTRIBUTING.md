# Contributing to VTrack

First off, thank you for considering contributing to VTrack! It's people like you that make VTrack a great tool.

## Code of Conduct

This project and everyone participating in it is governed by respect and professionalism. Please be kind and courteous.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the [issue list](https://github.com/josec-bckdev/vtrack/issues) as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps which reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed after following the steps**
* **Explain which behavior you expected to see instead and why**
* **Include logs and error messages**

**Bug Report Template:**

```markdown
**Environment:**
- OS: [e.g. Ubuntu 22.04]
- Python version: [e.g. 3.12]
- Docker version: [e.g. 24.0.0]

**Steps to Reproduce:**
1. ...
2. ...
3. ...

**Expected Behavior:**
...

**Actual Behavior:**
...

**Logs:**
```
[paste relevant logs]
```
```

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. Create an issue and provide the following information:

* **Use a clear and descriptive title**
* **Provide a step-by-step description of the suggested enhancement**
* **Provide specific examples to demonstrate the steps**
* **Describe the current behavior and explain which behavior you expected to see instead**
* **Explain why this enhancement would be useful**

### Pull Requests

* Fill in the required template
* Follow the Python style guide (PEP 8)
* Include appropriate test cases
* Update documentation as needed
* End all files with a newline

## Development Process

### 1. Fork & Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/josec-bckdev/vtrack.git
cd vtrack
```

### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Adding tests

### 3. Set Up Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-asyncio pytest-cov black flake8 mypy

# Start services
docker-compose up -d
```

### 4. Make Your Changes

* Write clean, readable code
* Follow PEP 8 style guide
* Add docstrings to functions and classes
* Use type hints where appropriate
* Keep changes focused and atomic

**Code Style Example:**

```python
from typing import Optional, List

def process_coordinates(
    coordinates: List[dict],
    zone_name: Optional[str] = None
) -> bool:
    """
    Process GPS coordinates and check for geofence violations.
    
    Args:
        coordinates: List of coordinate dictionaries
        zone_name: Optional zone name to filter by
        
    Returns:
        True if processing successful, False otherwise
        
    Raises:
        ValueError: If coordinates list is empty
    """
    if not coordinates:
        raise ValueError("Coordinates list cannot be empty")
    
    # Implementation here
    return True
```

### 5. Test Your Changes

```bash
# Run all tests
pytest app/tests/ -v

# Run with coverage
pytest app/tests/ --cov=app --cov-report=html

# Run microservice tests
cd microservices/notification-sender
pytest -v

# Check code style
black --check app/ microservices/
flake8 app/ microservices/

# Type checking
mypy app/ --ignore-missing-imports
```

### 6. Commit Your Changes

We use conventional commits for clear history:

```bash
# Format: <type>(<scope>): <subject>

git commit -m "feat(alerts): add email notification support"
git commit -m "fix(api): resolve coordinate validation bug"
git commit -m "docs(readme): update installation instructions"
git commit -m "test(alerts): add geofence boundary tests"
```

**Commit Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### 7. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear description of changes
- Reference to related issues (e.g., "Closes #123")
- Screenshots if UI changes
- Test results

**Pull Request Template:**

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## How Has This Been Tested?
Describe testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review performed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests added/updated
- [ ] All tests passing
- [ ] No breaking changes (or documented)
```

## Project Structure Guidelines

When adding new features, follow the existing structure:

```
app/                    # Main FastAPI application
├── main.py            # API routes
├── models.py          # Database models
├── database.py        # DB configuration
└── tests/             # Application tests

microservices/         # Independent services
├── alert-processor/   # Geofence detection
├── notification-sender/  # Alert delivery
└── [new-service]/     # Your new service

shared-package/        # Shared utilities
└── src/shared/
    └── message_queue.py

docs/                  # Documentation
├── architecture/
├── guides/
└── testing/
```

## Testing Guidelines

### Writing Tests

```python
import pytest
from app.main import app
from fastapi.testclient import TestClient

def test_api_endpoint():
    """Test description of what it validates"""
    # Arrange
    client = TestClient(app)
    
    # Act
    response = client.get("/api/endpoint")
    
    # Assert
    assert response.status_code == 200
    assert "expected_key" in response.json()
```

### Test Coverage

- Aim for >80% coverage
- Test happy paths and error cases
- Use meaningful test names
- Mock external dependencies

## Documentation Guidelines

* Update README.md if adding features
* Add docstrings to all functions/classes
* Update relevant docs in `docs/` folder
* Include code examples where helpful
* Keep documentation concise and clear

## CI/CD

All pull requests must pass:

✅ **Tests** - All pytest tests passing  
✅ **Docker Build** - Images build successfully  
✅ **Code Quality** - Linting and formatting checks  

GitHub Actions will automatically run these checks on your PR.

## Getting Help

* **Issues**: Search existing issues or create a new one
* **Discussions**: Use GitHub Discussions for questions
* **Documentation**: Check `docs/` folder

## Recognition

Contributors will be recognized in the project README and release notes.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to VTrack! 🚀
