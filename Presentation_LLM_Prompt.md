# LLM Master Prompt: Enterprise Presentation Generator for Multi-Agent Fraud Platform

Use the prompt below in any LLM (like Gemini 1.5 Pro, Claude 3.5 Sonnet, or GPT-4o) to generate a complete, professional presentation with rich diagrams, a latency budget Gantt chart, and system design visualizations.

---

```markdown
You are a Senior Solutions Architect, Enterprise Presentation Designer, and Technical Writer. 
Your goal is to build a comprehensive, production-grade presentation slide deck based on the technical specification of the **Real-Time Fraud Detection & Escalation Platform**.

This platform is a multi-agent system designed to evaluate financial transactions under a strict 100ms Service Level Agreement (SLA).

---

### SECTION 1: TECHNICAL SPECIFICATION CONTEXT

Here is the source architecture, latency budget, agent contracts, and operational guidelines:

#### 1. System Topology & Architecture
- **Ingress**: Spring Boot API Gateway (signature validation, payload normalization, Redis idempotency check).
- **Orchestrator**: LangGraph-based state machine managing parallel task dispatch, fast-path decisions, and specialist escalations.
- **Agent Cluster**:
  - **Tier-1 (Fast-Path)**: Blacklist Agent, Rule Agent, Customer Agent, ML Risk Agent (Random Forest model).
  - **Tier-2 (Specialists/Escalation)**: Geo Agent, Device Agent, Velocity Agent, LLM Reasoning Agent.
- **MCP Gateway Layer**: Gateway managing agent-tool connections via JSON-RPC, providing authentication, circuit breakers, rate limiting, and centralized tracing.
- **Decision Engine**: Combines agent inputs under strict Constitutional Governance Rules to produce the final transaction decision: `APPROVE`, `DECLINE`, or `ESCALATE`.
- **Egress**: Serializes payload back to the payment switch.
- **Asynchronous Feedback Pipeline**: High-throughput Kafka topics (`fraud.decisions`, `fraud.audit`, `fraud.feedback`, `fraud.chargebacks`) consume late-arriving dispute data. A Feedback Agent Cluster (Correlation, Drift Detection, Pattern Mining, Threshold Optimization) suggests updates.
- **Canary Deployment Pipeline**: Threshold updates run in Shadow Mode, then deploy progressively ($1\% \rightarrow 5\% \rightarrow 25\% \rightarrow 50\%$) to Blue-Green production.

#### 2. Latency Budget Allocation (100ms SLA Limit)
| Component / Layer | Category | Execution Mode | Budget (ms) | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Ingress Validation** | Input Ingestion | Sequential | 10ms | Payload checks, validation, and Redis idempotency filter. |
| **Orchestrator Setup** | Coordination | Sequential | 5ms | Future-scheduling and state context building. |
| **Blacklist Agent** | Parallel Evaluation | Parallel | 10ms | Card, device, and merchant lookup via MCP Gateway. |
| **Rule Agent** | Parallel Evaluation | Parallel | 5ms | Deterministic checks (sanctions list, channel limits). |
| **Customer Agent** | Parallel Evaluation | Parallel | 20ms | Trust profile retrieval and spending anomalies. |
| **ML Risk Agent** | Parallel Evaluation | Parallel | 25ms | Random Forest risk scoring service. |
| **Decision Engine** | Consensus / Governance | Sequential | 10ms | Weighted scoring synthesis & Constitutional Governance checks. |
| **Egress Response** | Output Delivery | Sequential | 5ms | Response payload serialization to POS/Switch. |
| **Reserve Buffer** | Safety Margin | Passive | 10ms | Safety margin for GC pauses and network jitter. |

*Note: Since Blacklist, Rule, Customer, and ML Risk Agents run in parallel, their total latency is bound by the slowest agent (ML Risk Agent = 25ms), not their sum. This keeps the execution timeline well below 100ms.*

#### 3. Constitutional Governance Rules
- `no_policy_override`: Governance policies unconditionally override agent recommendations.
- `no_hallucinated_facts`: Out-of-bounds metrics result in immediate validation failure.
- `evidence_required`: Critical risk signals must supply database logs.
- `max_agent_hops: 5` & `max_tool_calls: 3`: Prevents infinite orchestration recursion loops.
- `budget_enforced`: Latency budget monitor triggers fallback if elapsed time exceeds 80ms.
- `escalate_on_uncertainty`: Ambiguous classifications default to `ESCALATE` (triggering OTP or analyst queue).

---

### SECTION 2: PRESENTATION OUTLINE & SLIDE STRUCTURE

Generate a detailed 8-slide presentation. For each slide, write:
1. **Slide Metadata**: Title, Tagline/Category, and Slide Number.
2. **Visual Layout Guide**: Description of how this slide should be designed visually (e.g., grids, cards, colors).
3. **Core Slide Content**: Highly professional, technical bullet points and summaries. No placeholders.
4. **Mermaid.js Diagram**: A fully functional Mermaid diagram representing the concept of that specific slide.

#### Slide 1: Title & Overview
- **Content**: Title of the platform, the primary purpose (SLA compliance, multi-agent coordination), and a high-level system value proposition.
- **Visual**: A clean title hero card with indigo/cyan gradients.

#### Slide 2: The Challenge (Real-Time SLA & Asymmetric Risk)
- **Content**: Explain the payment switch requirements (100ms hard cap), asymmetric error costs (False Positives vs. False Negatives), and long-tail feedback delays.
- **Visual**: A 2-column comparative layout showing costs/impacts.

#### Slide 3: End-to-End Platform Architecture
- **Content**: Detail the processing flow from Ingress, through the Parallel Agent Cluster and the MCP Layer, to the Governance Engine and Egress.
- **Visual**: Include a **Mermaid.js Flowchart** showing the system topology, including the fast-path bypass.

#### Slide 4: Latency Budget Allocation & Parallel Timeline
- **Content**: Explain the categorization of latency (Ingestion, Coordination, Parallel Evaluation, Consensus, Delivery, Safety Buffer).
- **Visual**: Write a **Mermaid.js Gantt Chart** representing the timeline. Show that Ingress and Orchestrator run sequentially, the Tier-1 agents run in parallel (overlapping), followed by the sequential Decision Engine and Egress, with a tailing Reserve Buffer.
  * *Mermaid Gantt Tip*: Format it using `dateFormat x` or a simple relative scale (e.g., `0` to `100` milliseconds) to represent time clearly.

#### Slide 5: The Model Context Protocol (MCP) Gateway Layer
- **Content**: Explain tool abstraction, access control, trace telemetry, and circuit breaker mechanics for failing upstream microservices.
- **Visual**: A diagram or layout showing agents communicating with the MCP Gateway rather than direct APIs.

#### Slide 6: Agent Contracts & Interface Definitions
- **Content**: Show the input/output schemas of core agents (e.g., Blacklist, Customer, Geo).
- **Visual**: Formatted side-by-side JSON blocks or tables comparing the contracts.

#### Slide 7: Constitutional Governance Rules
- **Content**: Detail the safety guardrails, recursion bounds, evidence validation, and the fail-safe fallback modes.
- **Visual**: A table or grid displaying the rules with active/inactive indicators.

#### Slide 8: Asynchronous Optimization & Canary Deployment
- **Content**: Explain how the Kafka event pipeline feeds the Feedback Agent Cluster (Correlation, Drift, Threshold Optimization) and how Canary rollouts shadow and test the recommendations.
- **Visual**: Include a **Mermaid.js Flowchart** showing the lifecycle of a threshold update: Kafka Event -> Feedback Agents -> Shadow Mode -> Canary Stage (1% -> 5% -> 25% -> 50%) -> Blue-Green Promotion.

---

### SECTION 3: MERMAID.JS CODE GUIDELINES

Ensure all Mermaid diagrams:
1. Use standard syntax.
2. Wrap all node labels with parentheses or quotation marks to prevent syntax errors (e.g., `id1["Validation (10ms)"]`).
3. For the Gantt chart, use the following structure or similar:
   ```mermaid
   gantt
       title Transaction Latency Budget (100ms SLA Timeline)
       dateFormat  X
       axisFormat %s
       section Ingestion
       Ingress Validation : active, ingress, 0, 10
       Orchestrator Setup : active, orch, 10, 15
       section Evaluation
       Blacklist Agent (T1) : active, black, 15, 25
       Rule Agent (T1) : active, rules, 15, 20
       Customer Agent (T1) : active, customer, 15, 35
       ML Risk Agent (T1) : active, ml, 15, 40
       section Consensus
       Decision Engine : active, decide, 40, 50
       Egress Response : active, egress, 50, 55
       section Safety
       Reserve Buffer : active, reserve, 55, 65
   ```
4. Output raw markdown containing the presentation slides clearly.
```
