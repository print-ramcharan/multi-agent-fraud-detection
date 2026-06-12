# Project Guide: Multi-Agent Real-Time Fraud Detection & Escalation Platform

This repository contains the architecture design, latency allocations, and agent specifications for a production-grade, low-latency financial fraud detection platform.

---

## The Problem & Operational Context

In modern banking systems, processing card network transactions requires balancing speed with precision. The platform addresses several critical real-time engineering challenges:

1. **Strict Latency Constraints (100ms SLA)**: Payment switches require sync card authorization loops to complete within 100ms. If processing breaches this window, the transaction defaults or fails, causing high friction.
2. **Incomplete Information**: Critical outcome data (disputes, chargebacks, customer refunds) arrives days or weeks after a transaction is approved. Decisions must therefore be made in real-time based on local historical snapshots and dynamic profile calculations.
3. **Asymmetric Error Costs**:
   - *False Positive*: Rejecting a legitimate transaction leads to immediate revenue loss and severe customer friction.
   - *False Negative*: Approving a fraudulent transaction leads to direct chargeback fees, penalty interest, and compliance exposure.
4. **Agent Coordination**: Decoupling risk checks into specialist agents (Geo-location, Device Age, Velocity, Machine Learning Models, and Rule Engines) requires an efficient orchestration layer that runs checks in parallel and can abort/escalate gracefully before SLA exhaustion.

---

## Repository Guide & Shared Deliverables

When reviewing this solution, only the following files and directories are shared and should be read to understand the design:

1. **[README.md](file:///Users/ram/Desktop/multi-agent-fraud-detection/README.md)** (This document): The entry point detailing the problem statement, repository organization, files reading sequence, and developer prompts.
2. **[Solution.md](file:///Users/ram/Desktop/multi-agent-fraud-detection/Solution.md)**: The core system architecture design. It details the complete topology, latency budget tables, the Model Context Protocol (MCP) gateway specification, governance constitutions, and the asynchronous feedback loop.
3. **[Agents/](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents)**: Directory containing comprehensive specifications for each participating agent, including their default latency budgets, tools, execution mechanisms, and exact JSON schemas for inputs and outputs:
   - [Agents Overview](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/overview.md)
   - [Blacklist Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/blacklist_agent.md)
   - [Rule Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/rule_agent.md)
   - [Customer Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/customer_agent.md)
   - [ML Risk Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/ml_risk_agent.md)
   - [Geo Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/geo_agent.md)
   - [Device Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/device_agent.md)
   - [Velocity Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/velocity_agent.md)
   - [LLM Reasoning Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/llm_reasoning_agent.md)
   - [Guardrail Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/guardrail_agent.md)

---

## Repository Reference
- **GitHub Repository Link**: [https://github.com/ram/multi-agent-fraud-detection](https://github.com/ram/multi-agent-fraud-detection)

---

## Developer Prompts (Placeholders)

*These sections serve as placeholders for detailed generative prompts which will be added shortly.*

### 1. ChatGPT / Claude Master Prompt
This prompt is designed to instruct Claude or ChatGPT to understand the full domain requirements of the high-throughput payment network fraud detection platform.

````markdown
# Real-Time Fraud Detection and Escalation – Production-Grade Multi-Agent System

## Overview

Design a production-grade real-time fraud detection and escalation system for a high-throughput payment network. The system operates inline with card transactions and must make a decision before the payment authorization response is returned to the payment switch.

For every incoming transaction, the system must produce exactly one of the following outcomes:

* APPROVE – Allow the transaction to proceed.
* DECLINE – Block the transaction as suspected fraud.
* ESCALATE – Route the transaction for additional verification or review before a final decision is made.

The system sits between the point-of-sale (POS) terminal or online checkout and the issuer authorization response. The decision must be made under strict latency constraints while dealing with incomplete information, unreliable supporting services, and varying levels of transaction risk.

The exercise focuses on architecture, orchestration, reliability, explainability, and production-readiness rather than machine learning model development.

---

# Business Scenario

A national credit card network processes thousands of transactions per second on behalf of millions of cardholders.

The fraud operations team wants to deploy an intelligent fraud detection and escalation system capable of evaluating each transaction in real time and determining whether it should be:

1. Approved
2. Declined
3. Escalated for further verification

The system must operate inline with payment processing and therefore has a strict latency budget.

Transactions range from clearly legitimate to clearly fraudulent, with many ambiguous cases in between. The system must intelligently decide when to spend additional time gathering signals and when to return a decision immediately.

---

# Environment Constraints

The fraud detection system operates in a production payment environment where:

## Latency Requirements

Authorization decisions must be returned to the upstream payment switch within a strict latency budget.

Any additional investigation consumes part of that budget.

The system must continuously track remaining latency and decide whether deeper analysis is still affordable.

---

## Incomplete Information

At decision time, only information currently available can be used.

Long-tail fraud indicators such as:

* Chargebacks
* Customer disputes
* Confirmed fraud investigations

arrive hours or days later and are unavailable when the authorization decision is made.

The system must make decisions using only the data available at the time of the transaction.

---

## Asymmetric Error Costs

The cost of the two error types is not equal.

### False Positive

A legitimate transaction is blocked.

Consequences:

* Lost revenue
* Customer dissatisfaction
* Customer churn
* Increased support costs

### False Negative

A fraudulent transaction is approved.

Consequences:

* Financial losses
* Chargebacks
* Regulatory concerns
* Brand damage

The system must explicitly account for these differing business costs.

---

## Service Dependencies

The fraud system depends on multiple supporting services.

Examples include:

* Customer history systems
* Risk scoring services
* Geolocation services
* Verification systems
* Human analyst queues

Each service may:

* Fail
* Timeout
* Return incomplete information
* Become rate limited

The fraud detection system must continue operating safely even when one or more dependencies are unavailable.

---

## Operational Requirements

The system is expected to run continuously in production.

Requirements include:

* 24x7 availability
* Observability
* Debuggability
* Reliability
* Safe deployment practices

---

# Why This Problem Is Non-Trivial

The solution must address several competing concerns.

## 1. Latency vs Investigation Depth

Every additional service call consumes time.

The system must determine:

* When deeper investigation is justified
* When to stop gathering signals
* How remaining latency affects future decisions

---

## 2. Asymmetric Error Costs

False positives and false negatives affect the business differently.

Thresholds and decision policies must reflect these different costs.

---

## 3. Incomplete Information

The system must commit to a decision despite not having perfect information.

Waiting indefinitely is not possible.

---

## 4. Unreliable Supporting Services

External services and agents can:

* Timeout
* Fail
* Return partial results

The fraud system must degrade gracefully and continue making safe decisions.

---

## 5. Ambiguous Middle Ground

Many transactions are obviously safe or obviously fraudulent.

The difficult cases fall between these extremes.

The system must have a deliberate strategy for handling uncertain transactions.

---

## 6. Coordination Overhead

If multiple agents are used:

* Their responsibilities must be clearly defined.
* Communication must be controlled.
* Redundant work must be avoided.
* Runaway loops must be prevented.
* Latency growth must remain bounded.

---

## 7. Production-Grade Quality

Requirements such as:

* Auditability
* Observability
* Configurability
* Reliability
* Explainability

are first-class concerns, not afterthoughts.

---

# Core Problem Statement

Design and describe a production-grade end-to-end fraud detection and escalation system.

The system may use:

* A single intelligent agent
* Multiple specialized agents

For every transaction, the system must:

1. Receive the transaction.
2. Investigate risk signals.
3. Produce APPROVE, DECLINE, or ESCALATE.
4. Return the decision within the latency budget.
5. Provide a clear explanation for the decision.

The design must include:

* Lightweight checks
* AI-based signals and/or risk scores
* Escalation paths
* Failure handling
* Audit trails

---

# End-to-End Flow Requirements

The solution must describe the complete lifecycle of a transaction.

## 1. Ingress

Explain:

* How transactions enter the system
* Request validation
* Data normalization
* Queue, stream, or synchronous processing model

---

## 2. Orchestration

Explain:

* How control is handed to agents
* Budget allocation
* Sequential vs parallel execution
* Loop prevention
* Maximum investigation depth

---

## 3. Investigation

Explain:

* Which tools are called
* In what order
* Timeout policies
* Trigger conditions
* Signal collection strategy

---

## 4. Decision

Explain:

* How APPROVE, DECLINE, or ESCALATE is chosen
* How confidence is measured
* How explanations are generated
* How reasoning is recorded

---

## 5. Egress

Explain:

* How the decision is returned
* How latency guarantees are enforced

---

## 6. Post-Decision Actions

Explain asynchronous activities such as:

* OTP delivery
* Analyst notifications
* Logging
* Metric emission
* Audit persistence

---

## 7. Replay and Feedback

Explain:

* How historical decisions can be replayed
* How later outcomes are linked back
* How feedback improves future decisions

Possible feedback signals include:

* Confirmed fraud
* Analyst verdicts
* Chargebacks
* OTP success or failure
* Customer disputes

---

# Transaction Input Schema

Each transaction contains at least:

```json
{
  "transaction_id": "string",
  "card_id": "string",
  "customer_id": "string",
  "amount": 100.00,
  "currency": "USD",
  "merchant_id": "string",
  "merchant_category": "string",
  "location": {
    "country": "string",
    "city": "string",
    "coordinates": "optional"
  },
  "device_id": "string",
  "channel": "in-person | online | contactless | recurring",
  "timestamp": "ISO-8601"
}
```

# Available Tools and Data Sources

The system may call any of the following services.

## Customer History Service

Provides:

* Spending profile
* Historical transaction behavior
* Recent transaction history

---

## Geolocation Service

Provides:

* Distance from previous transaction
* Country risk information
* Location anomalies

---

## External Risk Scoring Service

Provides:

* Numeric fraud risk score

---

## Blacklist Service

Provides:

* Card blacklist status
* Merchant blacklist status
* Device blacklist status

---

## Verification Service

Provides:

* OTP verification
* Push notification verification
* Additional customer confirmation

---

## Human Analyst Queue

Provides:

* Manual investigation capability
* Escalation endpoint

---

# Multi-Agent Design Requirements

If multiple agents are used, the design must define:

## Topology

* Complete component diagram
* Agent relationships
* Call graph

---

## Agent Responsibilities

For every agent:

* Purpose
* Inputs
* Outputs
* Authority boundaries

---

## Communication Contract

Define:

* Message schema
* Agent interfaces
* Tool interfaces

---

## Orchestration Model

Choose and justify:

* Centralized orchestrator
* Supervisor model
* Peer-to-peer model
* Hybrid model

---

## Concurrency

Specify:

* Parallel calls
* Sequential calls
* Result reconciliation strategy

---

## Loop and Depth Control

Specify:

* Maximum agent hops
* Retry limits
* Investigation depth limits

---

## Budget Sharing

Specify:

* Latency allocation
* Per-agent time limits
* Tool budgets

---

## Failure Isolation

Specify:

* Behavior when an agent fails
* Behavior when a tool fails

---

## Determinism

Given identical inputs and identical tool responses, the system should produce identical decisions and explanations.

---

# Production-Grade Requirements

The system runs in a regulated environment.

The design must address:

## Latency

Defined per-transaction latency budget and enforcement strategy.

---

## Reliability

No single failure should silently produce an APPROVE decision.

Every dependency requires:

* Timeout policy
* Fallback policy

---

## Idempotency

Duplicate or replayed transaction requests must not produce:

* Different decisions
* Duplicate side effects
* Duplicate OTP requests

---

## Configurability

The following should be configurable rather than hardcoded:

* Thresholds
* Rule sets
* Agent topology
* Latency budgets

---

## Observability

Provide:

* Structured logs
* Metrics
* Traces
* Alerts

Metrics should include:

* Agent latency
* Tool latency
* Error rates
* Decision distributions
* Fallback usage

---

## Auditability

Every decision must generate a replayable audit record containing:

* Final decision
* Reason
* Signals consulted
* Agents involved
* Tool outputs
* Thresholds used
* Timing information

---

## Explainability

Every decision must include a human-readable explanation.

---

## Safety Controls

Include:

* Kill switches
* Circuit breakers
* Rate limiting
* Per-card controls
* Per-merchant controls

---

## Deployability

Support safe rollout methods such as:

* Canary deployments
* Shadow mode
* Feature flags
* A/B testing

---

## Security and Privacy

Protect sensitive information including:

* PAN/card data
* Device identifiers
* Location information

Data should be minimized and protected both in transit and at rest.

---

## Feedback Loop

The design must describe how future outcomes are collected and incorporated into the system.

Examples:

* Fraud confirmations
* Analyst outcomes
* OTP success/failure
* Customer disputes

---

# Functional Scenarios the Solution Must Handle

The system must demonstrate handling of:

1. Clearly fraudulent transactions that should be declined immediately.
2. Clearly legitimate transactions that should be approved immediately.
3. Transactions requiring deeper investigation.
4. Transactions with inconclusive signals.
5. Tool failures and timeouts.
6. Agent failures.
7. Partial data availability.
8. Duplicate or replayed transactions.
9. Selection of escalation channels.
10. Degraded mode operation when dependencies are unavailable.

---

# Out of Scope

Participants are NOT expected to:

* Train a machine learning fraud model.
* Build a real OTP delivery system.
* Build a biometric verification system.
* Build a human analyst console.
* Implement a complete stream-processing platform.
* Integrate with an actual payment network.
* Implement a specific agent framework.

Existing risk scoring services may be assumed.
````


### 2. Vibecoding Prompt
This prompt is designed to instruct an AI assistant to write code and build the prototype application.

````markdown
# Prompt: Build a Real-Time Fraud Detection Platform Prototype

You are a Principal Software Engineer and Distributed Systems Architect. Design and implement an end-to-end prototype of a Real-Time Fraud Detection Platform capable of processing financial transactions with low latency and high throughput.

The goal is to demonstrate scalable system design, event-driven architecture, distributed processing, and AI-assisted decision making.

The implementation should prioritize clean architecture, extensibility, observability, fault tolerance, and security.

## Tech Stack

Frontend:

* ReactJS
* TypeScript
* TailwindCSS
* React Query
* Recharts for dashboards

Backend:

* Node.js + Express (prototype)
* TypeScript

Messaging:

* Apache Kafka
* Kafka UI

Storage:

* PostgreSQL
* Redis

Infrastructure:

* Docker
* Docker Compose

Monitoring:

* Prometheus
* Grafana

Authentication:

* JWT Authentication

Optional AI:

* OpenAI API or local LLM integration

---

# Functional Requirements

The platform should simulate financial transactions and detect fraud in real time.

Users can:

* Generate transactions
* View transaction stream
* Observe fraud scores
* View alerts
* Monitor system metrics
* Review decisions

---

# System Architecture

## Components

### Transaction Generator Service

Responsibilities:

* Generate mock transactions
* Produce events to Kafka

Transaction schema:

```json
{
  "transactionId": "uuid",
  "userId": "user-123",
  "amount": 5000,
  "currency": "USD",
  "merchant": "Amazon",
  "country": "US",
  "deviceId": "device-001",
  "timestamp": "ISO8601"
}
```

Kafka Topic:

```text
transactions
```

---

### Fraud Detection Service

Consumes:

```text
transactions
```

Perform rule-based detection.

Rules:

1. Amount > $10,000

2. Multiple countries within 5 minutes

3. Multiple devices in short time

4. Excessive transaction frequency

5. Velocity checks

Compute:

```json
{
  "riskScore": 0-100,
  "reason": "High transaction amount"
}
```

Publish:

```text
fraud-decisions
```

---

### Decision Engine

Rules:

Risk Score:

0-30:
APPROVE

31-70:
OTP_REQUIRED

71-100:
BLOCK

Output:

```json
{
  "transactionId": "...",
  "decision": "BLOCK",
  "riskScore": 90,
  "reason": "Suspicious geo pattern"
}
```

---

### Notification Service

Consumes:

```text
fraud-decisions
```

Simulates:

* SMS
* Email
* Push Notification

Log notification events.

---

### Feedback Service

Allows fraud analysts to mark:

* True Positive
* False Positive

Store feedback in PostgreSQL.

Future model retraining can use this data.

---

# Kafka Topics

Create:

```text
transactions
fraud-decisions
alerts
feedback
notifications
```

Support:

* Partitioning
* Consumer groups
* Retry strategy
* Dead Letter Queue

DLQ:

```text
transactions-dlq
```

---

# PostgreSQL Schema

Users

```sql
users(
    id UUID PRIMARY KEY,
    name TEXT
)
```

Transactions

```sql
transactions(
    id UUID PRIMARY KEY,
    user_id UUID,
    amount DECIMAL,
    merchant TEXT,
    country TEXT,
    risk_score INT,
    decision TEXT,
    created_at TIMESTAMP
)
```

Feedback

```sql
feedback(
    id UUID PRIMARY KEY,
    transaction_id UUID,
    label TEXT,
    created_at TIMESTAMP
)
```

---

# Redis Usage

Use Redis for:

* User profiles
* Device history
* Velocity checks
* Recent transactions
* Rate limiting

TTL:

```text
5 minutes
15 minutes
1 hour
```

---

# Security Requirements

Implement:

* JWT Authentication
* RBAC (Admin/User)
* API rate limiting
* Input validation
* HTTPS ready configuration
* Secret management via environment variables

Never hardcode secrets.

---

# Reliability Requirements

Implement:

* Retry policies
* Exponential backoff
* Kafka consumer recovery
* Idempotent processing
* Graceful shutdown
* Health checks

Endpoints:

```text
/health
/ready
```

---

# Observability

Expose Prometheus metrics:

```text
transactions_processed_total
fraud_detected_total
consumer_lag
api_requests_total
processing_latency_ms
```

Visualize in Grafana.

---

# React Dashboard

Pages:

## Login

JWT login.

---

## Dashboard

Cards:

* Transactions processed
* Fraud detected
* System health
* Consumer lag

Real-time updates via WebSocket.

---

## Transaction Stream

Live stream of Kafka events.

Columns:

* Transaction ID
* Amount
* Merchant
* Country
* Risk Score
* Decision

Color coding:

Green:
APPROVED

Yellow:
OTP_REQUIRED

Red:
BLOCKED

---

## Fraud Analytics

Charts:

* Fraud by country
* Risk score distribution
* Transactions per minute
* Decision breakdown

---

## Analyst Console

Allow analysts to:

* Review transactions
* Override decisions
* Submit feedback

---

# Docker Compose Services

Create containers for:

```text
react-ui
api-gateway
transaction-generator
fraud-service
decision-engine
notification-service
feedback-service
postgres
redis
zookeeper
kafka
kafka-ui
prometheus
grafana
```

All services should communicate through Docker networks.

---

# Non Functional Requirements

Target:

* 1000+ TPS in prototype
* Horizontal scalability
* Fault tolerance
* Stateless services
* Event-driven communication
* Easy future migration to Kubernetes

---

# Future Enhancements

Design the architecture so future integrations are easy:

* Apache Flink
* Apache Spark Streaming
* ML Models
* LLM Reasoning Agent
* Guardrail Agent
* MCP Servers
* Feature Store
* Kubernetes Deployment
* Multi-region replication

---

# Deliverables

Generate:

1. Monorepo structure
2. Docker Compose file
3. Kafka configuration
4. Backend microservices
5. React frontend
6. PostgreSQL migrations
7. Redis integration
8. Prometheus metrics
9. Grafana dashboards
10. README with setup instructions

Generate code incrementally, starting with Docker Compose and infrastructure setup first.
````

