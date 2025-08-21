# RAQ.AI Document Generation Service

A sophisticated document generation pipeline using AutoGen agents for content planning and production.

## Environment Setup

This project uses **Python 3.11.6** with **pyenv** for version management and a virtual environment for dependency isolation.

### Quick Start

1. **Activate the environment:**
   ```bash
   ./activate_env.sh
   ```

2. **Or manually:**
   ```bash
   eval "$(pyenv init -)"
   source venv/bin/activate
   ```

### Development Setup

#### Prerequisites
- **pyenv** (for Python version management)
- **Python 3.11.6** (managed by pyenv)

#### Initial Setup (Already Done)
```bash
# Set Python version
pyenv local 3.11.6

# Create virtual environment
python -m venv venv

# Install dependencies
pip install -r requirements.txt
```

#### Key Dependencies
- **AutoGen**: `autogen-agentchat`, `autogen-ext`, `autogen-core`
- **OpenAI**: `openai`, `tiktoken`
- **Web Scraping**: `httpx`, `beautifulsoup4`, `html2text`
- **Configuration**: `PyYAML`
- **Development**: `pytest`, `black`, `flake8`, `jupyter`

## Project Structure

```
src/doc-gen/
├── pipeline_runner.py          # Main pipeline orchestrator
├── process_analysis_runner.py  # Process analysis component
├── Content_Planning_Team.yaml  # Planning team configuration
├── Content_Production_Team.yaml # Production team configuration
├── Process_Analysis_Team.yaml  # Analysis team configuration
├── tools_config.yaml          # Tools and functions config
└── content_briefs/            # Brand content brief templates
    ├── payment_comparisons.md
    └── payment_termonology.md

# Root-level runner files
run-planning.py                 # Planning-only workflow runner
run-pipeline.py                 # Full pipeline runner (Planning → Production → Analysis)
run-production.py               # Production-only runner (rerun production from existing planning)
job_utils.py                   # Job ID management utilities
jobid.txt                      # Sequential job ID tracker (0001, 0002, etc.)
output/                        # Generated job folders (0001/, 0002/, etc.)
```

## Usage

### Running the Workflows

```bash
# Navigate to the project
cd /Users/erik/RAQ/Raq.Ai

# Activate environment
./activate_env.sh

# Run different workflows
python run-planning.py          # Planning only
python run-pipeline.py          # Full pipeline  
python run-production.py        # Production-only (rerun from existing planning)
```

### VS Code Debug Configurations

The project includes three debug configurations in `.vscode/launch.json`:

1. **RAQ.AI Planning Runner** - Debug `run-planning.py`
2. **RAQ.AI Full Pipeline Runner** - Debug `run-pipeline.py`  
3. **RAQ.AI Production-Only Runner** - Debug `run-production.py`

### Runner Configuration

Each runner has configuration constants at the top of the file:

```python
# Edit these constants as needed
USER_INPUT = "Create a comprehensive guide about..."
TEMPLATE_URL = None  # Optional
CONTENT_BRIEF_TYPE = "payment_comparisons"

# For production-only runner:
TARGET_JOB_ID = 2  # Rerun production using job 0002's planning output

## Usage

### Running the Pipeline

```bash
# Navigate to the project
cd /Users/erik/RAQ/Raq.Ai

# Activate environment
./activate_env.sh

# Run the pipeline (example)
cd src/doc-gen
python pipeline_runner.py
```

### Development Tools

```bash
# Code formatting
black .

# Linting
flake8 .

# Testing
pytest

# Jupyter Lab (for interactive development)
jupyter lab
```

### Environment Management

The project uses:
- **pyenv**: Python version management (3.11.6)
- **venv**: Virtual environment isolation
- **requirements.txt**: Dependency management

#### Key Files
- `.python-version`: Pyenv configuration (3.11.6)
- `requirements.txt`: Python dependencies
- `activate_env.sh`: Environment activation script
- `.gitignore`: Git exclusions

## Pipeline Components

### 1. Content Planning Team
- **File**: `Content_Planning_Team.yaml`
- **Purpose**: Creates article outlines, SEO keywords, research data
- **Agents**: Planning specialists with different roles

### 2. Content Production Team  
- **File**: `Content_Production_Team.yaml`
- **Purpose**: Generates final content based on planning artifacts
- **Agents**: Writers, editors, markdown specialists

### 3. Process Analysis Team
- **File**: `Process_Analysis_Team.yaml`
- **Purpose**: Analyzes workflow patterns and optimization
- **Agents**: Process analysts and improvement specialists

### Tools Configuration
- **File**: `tools_config.yaml`
- **Functions**: Web scraping, content analysis, etc.
- **Integration**: Dynamic tool loading for agents

## Environment Status ✅

- [x] Python 3.11.6 (pyenv)
- [x] Virtual environment created
- [x] All dependencies installed
- [x] AutoGen packages working
- [x] Pipeline runner tested
- [x] Development tools ready

## Next Steps

1. **Configure OpenAI API**: Set your `OPENAI_API_KEY` environment variable
2. **Test Pipeline**: Run a complete workflow test
3. **Content Briefs**: Customize content brief templates
4. **Team Configuration**: Adjust agent roles and prompts as needed

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated
2. **Python Version**: Check `python --version` shows 3.11.6
3. **Dependencies**: Run `pip install -r requirements.txt` if packages missing
4. **Environment**: Use `./activate_env.sh` to properly set up the environment

### Environment Reset
```bash
# Remove virtual environment
rm -rf venv

# Recreate
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
