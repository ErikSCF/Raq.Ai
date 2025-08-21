"""
Step extraction utilities for AutoGen workflow processing.
Handles step file summarization, agent flow extraction, and agent result content preparation.
"""

import re
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, OrderedDict
from openai import AsyncOpenAI


def parse_conversation_sections(content: str) -> OrderedDict[str, str]:
    """Parse conversation content into structured agent sections using regex."""
    agent_messages = OrderedDict()
    
    # Pattern to match <!--- SECTION: AGENT_NAME ---> ... <!--- END SECTION: AGENT_NAME --->
    section_pattern = r'<!---\s*SECTION:\s*([^-]+?)\s*--->(.*?)<!---\s*END\s+SECTION:\s*\1\s*--->'
    
    # Find all agent sections
    matches = re.findall(section_pattern, content, re.DOTALL | re.IGNORECASE)
    
    for agent_name, message_content in matches:
        agent_name = agent_name.strip()
        message_content = message_content.strip()
        
        # Skip the outer wrapper section
        if 'CONVERSATION LOG' in agent_name.upper():
            continue
            
        agent_messages[agent_name] = message_content
    
    return agent_messages


async def ai_summarize_agent_content(agent_name: str, content: str) -> str:
    """Use AI to create an intelligent summary of agent content."""
    if len(content) <= 300:
        return content
    
    try:
        client = AsyncOpenAI()
        
        prompt = f"""Analyze this {agent_name} agent's contribution and create a concise summary focusing on:

1. **Key Actions Taken**: What specific actions or decisions did this agent make?
2. **Content Created/Modified**: What content was generated, changed, or refined?
3. **Feedback/Rejections**: Any feedback given or content rejected, and why?
4. **Important Outcomes**: Critical results, completions, or next steps identified

Agent Content:
{content}

Provide a structured summary in 3-4 bullet points, focusing on concrete actions and outcomes rather than generic descriptions."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"  ⚠ AI summarization failed for {agent_name}, using fallback: {e}")
        # Fallback to truncated content
        lines = content.split('\n')
        return '\n'.join(lines[:3]) + "..." if len(lines) > 3 else content


def ai_summarize_agent_content_sync(agent_name: str, content: str) -> str:
    """Synchronous wrapper for AI summarization."""
    if len(content) <= 300:
        return content
    
    try:
        # Use synchronous OpenAI client
        from openai import OpenAI
        client = OpenAI()
        
        prompt = f"""Analyze this {agent_name} agent's contribution and create a concise summary focusing on:

1. **Key Actions Taken**: What specific actions or decisions did this agent make?
2. **Content Created/Modified**: What content was generated, changed, or refined?
3. **Feedback/Rejections**: Any feedback given or content rejected, and why?
4. **Important Outcomes**: Critical results, completions, or next steps identified

Agent Content:
{content}

Provide a structured summary in 3-4 bullet points, focusing on concrete actions and outcomes rather than generic descriptions."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"  ⚠ AI summarization failed for {agent_name}, using fallback: {e}")
        # Fallback to truncated content
        lines = content.split('\n')
        return '\n'.join(lines[:3]) + "..." if len(lines) > 3 else content


def create_agent_flow_summary(agent_messages: OrderedDict[str, str]) -> str:
    """Create a visual flow diagram and AI-powered summary from parsed agent messages."""
    if not agent_messages:
        return "No agent interactions found"
    
    # Create flow diagram
    agent_names = list(agent_messages.keys())
    flow_diagram = " → ".join(agent_names)
    
    # Create detailed summary with AI-powered content analysis
    summary_parts = [f"### Agent Flow Diagram\n```\n{flow_diagram}\n```\n"]
    summary_parts.append("### Agent Contributions:")
    
    for agent_name, content in agent_messages.items():
        # Use AI summarization for long content, keep short content as-is
        if len(content) > 500:
            print(f"  🤖 AI summarizing {agent_name} content ({len(content)} chars)...")
            content_summary = ai_summarize_agent_content_sync(agent_name, content)
        else:
            content_summary = content
        
        summary_parts.append(f"\n**{agent_name}:**")
        summary_parts.append(f"```\n{content_summary}\n```")
    
    return '\n'.join(summary_parts)


def prepare_step_file_summaries(output_dir: str, team_name: str, step_files: Optional[List[str]] = None) -> str:
    """Extract and provide step file content for context injection into analysis teams."""
    summaries = []
    
    # Use step files from workflow configuration
    target_step_files = step_files or []
    
    job_folder = Path(output_dir)
    for step_file in target_step_files:
        file_path = job_folder / step_file
        if file_path.exists():
            try:
                # Read the step file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse the conversation into structured agent messages
                agent_messages = parse_conversation_sections(content)
                
                if agent_messages:
                    # Create a structured summary with agent flow
                    structured_summary = create_agent_flow_summary(agent_messages)
                    summaries.append(f"=== {step_file.upper()} ===\n{structured_summary}")
                    print(f"  ✓ Parsed {len(agent_messages)} agent sections from: {step_file}")
                else:
                    # Fallback to raw content if parsing fails
                    if len(content) > 15000:
                        content = content[:15000] + "\n\n[Content truncated for context efficiency...]"
                    summaries.append(f"=== {step_file.upper()} ===\n{content}")
                    print(f"  ⚠ Could not parse agent sections, using raw content: {step_file}")
                
            except Exception as e:
                print(f"  ⚠ Error reading step file {step_file}: {e}")
        else:
            print(f"  ⚠ Step file not found: {step_file}")
    
    return '\n\n'.join(summaries) if summaries else ""


def extract_agent_flow_from_steps(steps_content: str) -> str:
    """Extract agent interaction flow from conversation steps, similar to older system."""
    if not steps_content:
        return "No conversation steps found"
    
    lines = steps_content.split('\n')
    agent_interactions = []
    
    # Define non-agent entries to filter out (from older system)
    non_agents = {'user', 'System', 'Pros', 'Cons', 'TaskResult', 'FunctionCall', 'FunctionExecutionResult'}
    
    for line in lines:
        agent_name = None
        
        # Look for agent indicators in various formats
        if line.strip().startswith('[') and line.strip().endswith(']:'):
            # Format: [agent_name]:
            agent_name = line.strip()[1:-2].strip()
        elif line.strip().startswith('*AGENT:') and line.strip().endswith('*'):
            # Format: *AGENT: agent_name*
            agent_name = line.strip()[7:-1].strip()
        elif '<!--- SECTION:' in line and line.strip().endswith('--->'):
            # Format: <!--- SECTION: AGENT_NAME --->, <!--- SECTION: EPIC AGENT --->, etc.
            parts = line.split('SECTION:')[1].split('--->')[0].strip()
            # Clean up the agent name and exclude non-agent sections
            agent_name = parts.strip()
            # Skip USER sections and other non-agent entries
            if agent_name.upper() in ['USER', 'SYSTEM']:
                agent_name = None
        
        if agent_name and agent_name not in non_agents and agent_name not in agent_interactions:
            agent_interactions.append(agent_name)
    
    if agent_interactions:
        flow = ' → '.join(agent_interactions)
        return f"Agent Flow: user → {flow}"
    else:
        return "No agent interactions found"


def prepare_agent_result_content(team_config: Dict, job_folder: Path) -> str:
    """Load agent result content from previous team for context injection."""
    agent_result_file = team_config.get('agent_result')
    
    if not agent_result_file:
        return ""
    
    file_path = job_folder / agent_result_file
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Truncate if too long to prevent token overflow
            if len(content) > 2000:
                content = content[:2000] + "\n\n[Content truncated for context efficiency...]"
            
            print(f"  ✓ Loaded agent result: {agent_result_file}")
            return f"=== PREVIOUS TEAM RESULT ===\n{content}"
            
        except Exception as e:
            print(f"  ⚠ Error reading agent result {agent_result_file}: {e}")
    else:
        print(f"  ⚠ Agent result file not found: {agent_result_file}")
    
    return ""


def extract_conversation_summary(conversation_steps: str, max_length: int = 1500) -> str:
    """Extract a summary of conversation steps for context injection."""
    if not conversation_steps:
        return "No conversation steps available"
    
    # If content is short enough, return as-is
    if len(conversation_steps) <= max_length:
        return conversation_steps
    
    # Extract key sections for summary
    lines = conversation_steps.split('\n')
    summary_lines = []
    
    for line in lines:
        # Keep agent indicators and key decision points
        if (line.strip().startswith('[') and line.strip().endswith(']:')) or \
           ('AGENT:' in line.upper()) or \
           ('DECISION:' in line.upper()) or \
           ('RESULT:' in line.upper()) or \
           ('FEEDBACK:' in line.upper()):
            summary_lines.append(line)
    
    summary = '\n'.join(summary_lines)
    
    # If still too long, truncate with indication
    if len(summary) > max_length:
        summary = summary[:max_length] + "\n\n[Summary truncated for context efficiency...]"
    
    return summary
