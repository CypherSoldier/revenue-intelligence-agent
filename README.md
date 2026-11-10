# Revenue Investigation Agent

A lightweight MVP for an agentic analytics assistant that turns a business question into a safe, read-only investigation workflow. It interprets the ask, plans the analysis, checks approved data, and summarizes evidence-backed findings.

## MVP
- Natural-language revenue questions
- Read-only SQL investigation against approved data
- Step-by-step analysis with validation and retry logic
- Clear findings with supporting evidence and caveats
- Optional Slack-ready summary for review

### The Architecture
Built on an "Agentic Loop" (Observe $\rightarrow$ Plan $\rightarrow$ Act $\rightarrow$ Reflect).   

### How it behaves
Goal-oriented instead of prompt-oriented. Instead of asking "Write me a SQL query," you tell it "Find why our revenue dropped in Q2 and post a summary to Slack." The system decides which database to query, runs the code, inspects the errors, retries, and formats the result autonomously.  

### Real-world Example
Devin / AutoGPT / Claude Computer Use: Software that executes multi-step workflows over extended periods with minimal human intervention.   

## Demo
<!--
<div align="center">
  <img src="./demo/dashboard_concept_1.png" alt="Dashboard concept 1" width="100%" />
  <br /><br />
  <img src="./demo/dashboard_concept_2.png" alt="Dashboard concept 2" width="100%" />
</div>
-->