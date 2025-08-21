# RAQ.AI Document Generation System - Claude Context Guide

## System Overview

RAQ.AI is an AutoGen-powered document generation pipeline that uses AI agent teams to create structured project planning documents. The system is designed around multi-agent workflows with dynamic team configurations defined in YAML files.

## Core Architecture

### Environment Setup
- **Python Version**: 3.11.6 managed by pyenv
- **Environment Activation**: Use `./activate_env.sh` to switch pyenv and activate virtual environment
- **Dependencies**: AutoGen framework, OpenAI, ChromaDB for vector memory, web scraping tools

### Project Structure
```
/Users/erik/RAQ/Raq.Ai/
├── activate_env.sh                 # Environment activation script
├── run-pipeline.py                 # Main executable - configurable workflow runner
├── job_utils.py                   # Job ID management utilities  
├── jobid.txt                      # Sequential job ID tracker (0060, 0061, etc.)
├── src/doc-gen/
│   ├── pipeline_runner.py         # Core AutoGen pipeline orchestrator
│   ├── process_analysis_runner.py # Process analysis component
│   ├── documents/RAQ/             # RAQ document type configuration
│   │   ├── workflow.yaml          # Team execution order & dependencies
│   │   ├── Epic_Discovery_Team.yaml
│   │   ├── Content_Analysis_Team.yaml
│   │   ├── Content_Planning_Team.yaml
│   │   └── Content_Production_Team.yaml
├── assets/                        # Input assets (PDFs, docs)
├── output/                        # Generated job output folders
│   ├── 0060/                     # Job-specific output directory
│   ├── 0061/
│   └── 0075/
└── expected/                      # Expected output samples
```

### Team Configuration System

### YAML Configuration Structure

#### 1. Workflow Configuration (`workflow.yaml`)
Defines team execution order and dependencies:
```yaml
workflow:
  name: "RAQ Document Generation"
  teams:
    - name: "Epic_Discovery_Team"
      output_file: "epic_discovery_output.md"
      depends_on: []  # No dependencies - first team
      input_files: []
    - name: "Content_Analysis_Team" 
      output_file: "epic_discovery_analysis.md"
      depends_on: ["Epic_Discovery_Team"]
      input_files:
        - "epic_discovery_output_steps.md"
```

#### 2. Team Configuration (`*_Team.yaml`)
Each team YAML defines:
- **Team Label**: Human-readable team name
- **Selector Prompt**: Logic for choosing next agent to act
- **Participants**: Agent definitions with roles, tools, system messages
- **Config**: Model settings, termination conditions, memory limits

#### 3. Template Variable Handling
**CRITICAL**: The selector prompt supports both custom and AutoGen built-in template variables:

**AutoGen Built-in Variables** (handled automatically by AutoGen):
- `{roles}` - List of participant roles/names
- `{history}` - Conversation history
- `{participants}` - List of participant names

**Custom Variables** (handled by pipeline runner):
- `{input_files}` - List of input files for the team

**Implementation**: The pipeline runner uses `string.replace()` instead of `string.format()` to avoid interfering with AutoGen's template variable handling:
```python
# CORRECT: Selective replacement preserving AutoGen variables
selector_prompt = selector_prompt.replace('{input_files}', str(files_list))

# WRONG: This would break AutoGen's {roles}, {history}, {participants}
selector_prompt = selector_prompt.format(input_files=str(files_list))
```

### Agent Types & Tools
- **Epic Analyst**: Extracts functional requirements, creates epic matrices
- **Quality Specialists**: Validate completeness and format
- **Story Writers**: Create detailed user stories with acceptance criteria  
- **Markdown Formatters**: Convert to clean markdown output
- **File Readers**: Load existing files using `read_file` tool
- **Workflow Analyzers**: Analyze agent interaction patterns

## Execution System

### Job Management
- **Job IDs**: Sequential numbers (0060, 0061, 0075, etc.) stored in `jobid.txt`
- **Output Structure**: Each job creates dedicated folder in `/output/`
- **Asset Management**: Assets copied to job-specific `/assets/` subfolder

### Pipeline Execution
1. **Configuration Loading**: Load workflow.yaml and team YAML files
2. **Job Setup**: Create job directory, copy assets
3. **Sequential Team Execution**: Run teams based on dependency graph
4. **Output Generation**: Save team outputs and conversation steps

### Running the System
```bash
# Activate environment
./activate_env.sh

# Full workflow with new job ID
python run-pipeline.py

# Rerun existing job  
python run-pipeline.py --rerun 0061

# Start from specific team
python run-pipeline.py --rerun 0061 --start-from Content_Analysis_Team
```

### Global Configuration Variables
The `run-pipeline.py` file has configuration variables at the top:
```python
RERUN_JOB_ID = "0061"  # Set to rerun existing job
START_FROM_TEAM = "Content_Analysis_Team"  # Set to start from specific team
```

## AutoGen Integration

### Key AutoGen Components
- **SelectorGroupChat**: Manages agent selection using selector prompts
- **AssistantAgent**: Individual AI agents with specific roles
- **OpenAIChatCompletionClient**: GPT-4 model integration
- **ChromaDBVectorMemory**: Vector memory for asset access
- **FunctionTool/StaticWorkbench**: Tool integration for file operations

### Team Orchestration
1. **Dynamic Team Creation**: YAML configs converted to AutoGen teams at runtime
2. **Dependency Management**: Teams execute in order based on `depends_on` field
3. **File Handoffs**: Output files become input files for dependent teams
4. **Conversation Memory**: Limited context windows to prevent overflow

## Development Workflow

### Making Changes
1. **Team Configuration**: Edit YAML files in `src/doc-gen/documents/RAQ/`
2. **Pipeline Logic**: Modify `src/doc-gen/pipeline_runner.py`
3. **Execution Control**: Update `run-pipeline.py` configuration variables
4. **Testing**: Use `--rerun` and `--start-from` for iterative development

### Environment Management
- Always run `./activate_env.sh` before development
- Use pyenv for Python version consistency
- Virtual environment isolates dependencies

### Output Analysis
- **Job Outputs**: Check `/output/{job_id}/` for generated documents
- **Conversation Steps**: Review `*_steps.md` files for agent interactions
- **Process Analysis**: Use Content_Analysis_Team to analyze workflow effectiveness

## Current Capabilities

### Document Types
- **RAQ**: Project planning documents with epic discovery and analysis
- **Extensible**: Framework supports additional document types

### Team Types  
- **Epic Discovery**: Functional requirement extraction and epic creation
- **Content Analysis**: Workflow pattern analysis and recommendations
- **Content Planning**: Strategic content planning (configurable)
- **Content Production**: Document generation (configurable)

### Tools Integration
- **File Operations**: Read/write files, asset management
- **Web Scraping**: Content analysis from URLs
- **Vector Memory**: Semantic search over project assets
- **Markdown Generation**: Professional document formatting

## Key Files to Monitor
- `src/doc-gen/documents/RAQ/workflow.yaml` - Team execution order
- `src/doc-gen/documents/RAQ/*_Team.yaml` - Individual team configurations  
- `run-pipeline.py` - Main execution script with configuration variables
- `src/doc-gen/pipeline_runner.py` - Core AutoGen orchestration logic
- `jobid.txt` - Current job sequence number
- `output/{job_id}/` - Generated outputs for specific jobs

## Development Tips
- Use job reruns for iterative development: `--rerun {job_id} --start-from {team}`
- Monitor conversation steps files to debug agent interactions
- Adjust team configurations in YAML files for behavior changes
- Use vector memory sparingly to avoid context overflow
- Keep agent system messages focused and specific to roles

This system enables sophisticated multi-agent document generation with configurable workflows, dependency management, and comprehensive output tracking.
