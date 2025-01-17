# Contributing to FluxComfyUIBot

Thank you for your interest in contributing to FluxComfyUIBot! This document provides guidelines and instructions for contributing to the project.

## Table of Contents
1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Code Style Guidelines](#code-style-guidelines)
4. [Making Contributions](#making-contributions)
5. [Testing](#testing)
6. [Documentation](#documentation)
7. [Pull Request Process](#pull-request-process)

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/FluxComfyUIBot.git
   cd FluxComfyUIBot
   ```
3. Set up your development environment

## Development Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env_example` to `.env` and configure your environment variables


### Project Structure
```
FluxComfyUIBot/
├── Main/
│   ├── custom_commands/    # Command implementations
│   └── utils/             # Utility functions
├── docs/                  # Documentation
├── tests/                # Test files
└── security/             # Security-related code
```

### Code Organization
1. **Modularity**
   - Break down code into small, reusable functions
   - Keep functions focused on single responsibility
   - Use appropriate design patterns

2. **Type Safety**
   ```python
   from typing import List, Optional, Dict

   def process_data(input_data: Dict[str, str]) -> Optional[List[str]]:
       # Implementation
       pass
   ```

3. **Error Handling**
   ```python
   try:
       result = process_data(input_data)
   except CustomException as e:
       logging.error(f"Error processing data: {e}")
       raise
   ```

## Making Contributions

1. Create a new branch for your feature:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following these principles:
   - Write clean, documented code
   - Include type hints
   - Add appropriate error handling
   - Include unit tests
   - Update documentation

3. Commit your changes:
   ```bash
   git commit -m "feat: add new feature description"
   ```

   Follow conventional commits format:
   - feat: New feature
   - fix: Bug fix
   - docs: Documentation changes
   - style: Code style changes
   - refactor: Code refactoring
   - test: Adding tests
   - chore: Maintenance tasks

## Testing

1. Write tests for new features:
   ```python
   def test_new_feature():
       # Arrange
       input_data = {"key": "value"}
       
       # Act
       result = process_data(input_data)
       
       # Assert
       assert result is not None
   ```

2. Run tests before submitting:
   ```bash
   python -m pytest
   ```

## Documentation

1. Add docstrings to all functions and classes:
   ```python
   def process_data(input_data: dict) -> Optional[list]:
       """
       Process the input data and return results.

       Args:
           input_data (dict): Input data to process

       Returns:
           Optional[list]: Processed data or None if processing fails

       Raises:
           ValueError: If input_data is invalid
       """
       pass
   ```

2. Update README.md when adding new features
3. Keep API documentation up to date

## Pull Request Process

1. Update the README.md with details of changes if applicable
2. Update the documentation with details of changes
3. Ensure all tests pass
4. Request review from maintainers
5. Address review comments

### PR Checklist
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] Type hints included
- [ ] Error handling implemented
- [ ] No sensitive information included
- [ ] Branch is up to date with main

## Questions or Need Help?

Feel free to open an issue for:
- Bug reports
- Feature requests
- Questions about the codebase
- Contribution guidance

Thank you for contributing to FluxComfyUIBot!
