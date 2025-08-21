# Development environment setup script
# Run this script to activate the virtual environment and set up the project

#!/bin/bash

# Activate pyenv
eval "$(pyenv init -)"

# Activate virtual environment
source venv/bin/activate

# Display environment info
echo "✅ Environment Setup Complete!"
echo "Python version: $(python --version)"
echo "Virtual environment: $(which python)"
echo ""
echo "📦 Available Commands:"
echo "  - python src/doc-gen/pipeline_runner.py"
echo "  - jupyter lab (for development)"
echo "  - pytest (for running tests)"
echo "  - black . (for code formatting)"
echo "  - flake8 . (for linting)"
echo ""
echo "🚀 You're ready to develop!"
