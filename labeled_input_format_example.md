# New Labeled Input Format (Legacy-Free)

## ❌ Old Legacy Format (REMOVED):
```yaml
teams:
  - id: "document_assembly"
    input_files:
      - "epic_discovery.md"
    step_files: []
    agent_result: null

  - id: "epic_analysis"
    input_files: []
    step_files:
      - "epic_discovery.steps.md"
    agent_result: null
```

## ✅ New Clean Format (ONLY SUPPORTED):
```yaml
teams:
  - id: "document_assembly"
    labeled_inputs:
      - ["Epic Discovery Content", "epic_discovery.md"]
      - ["Content Brief", "brand_content_brief.md"]  # Must be explicitly included

  - id: "epic_analysis"
    labeled_inputs:
      - ["Step Summaries", "epic_discovery.steps.md"]
      - ["Epic Results", "epic_discovery.md"]
      - ["Content Brief", "brand_content_brief.md"]  # Must be explicitly included
```

## Content Injection:

### ❌ Old System Message Template Variables (REMOVED):
```yaml
system_message: |
  You have access to:
  {input_files}
  
  Previous process analysis:
  {step_summaries}
  
  Agent results:
  {agent_result}
```

### ✅ New User Message Approach (ONLY SUPPORTED):
**Clean system messages with no template variables:**
```yaml
system_message: |
  You are an expert analyst. Analyze the provided content and create comprehensive documentation.
```

**All labeled inputs go into the user/task message:**

**User Message Output:**
```
Here is the task: [task description]

<%-- Input: Epic Discovery Content --%>
# Epic Discovery Results
[epic discovery content here...]
<%-- End Input: Epic Discovery Content --%>

<%-- Input: Step Summaries --%>
=== EPIC_DISCOVERY.STEPS.MD ===
SELECTOR: Starting conversation...
ANALYST AGENT: Beginning analysis...
<%-- End Input: Step Summaries --%>

<%-- Input: Content Brief --%>
# Brand Content Brief
[brand content brief here...]
<%-- End Input: Content Brief --%>
```

## Benefits:
1. **🧹 Pure Architecture** - Zero template variable injection, all content in user messages
2. **🏷️ Explicit Content Declaration** - All content must be explicitly declared in `labeled_inputs`
3. **📨 User Message Approach** - Clean system messages, all labeled inputs in user/task message
4. **🔍 Tagged Content Boundaries** - Input tags `<%-- Input: ... --%>` provide clear content boundaries
5. **🚫 No Magic** - No automatic content brief injection or template variable replacement
6. **⚡ Simplified Logic** - All content follows the same labeled input pattern in user messages
7. **📋 Consistent Configuration** - Content brief is just another labeled input like any other
8. **🎯 Single Injection Point** - Only `_prepare_task_message()` handles content inclusion
