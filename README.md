<div align="center">

# AI Integration Research Agent

### Evidence-first integration intelligence across 100 modern apps

A local-LLM research pipeline that discovers API and authentication capabilities,
grounds findings in web evidence, normalizes the results, verifies a risk-prioritized
sample, and turns the research into actionable Product Ops insights.

<br/>

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](#)
[![LLM](https://img.shields.io/badge/LLM-Qwen3%208B-7C3AED?style=for-the-badge)](#)
[![Apps](https://img.shields.io/badge/Apps-100-111827?style=for-the-badge)](#)
[![Evidence](https://img.shields.io/badge/Evidence-527-111827?style=for-the-badge)](#)
[![Verified](https://img.shields.io/badge/Verified-10%20Apps-176B45?style=for-the-badge)](#)

<br/><br/>

<a href="./case_study.html">
  <img src="https://img.shields.io/badge/%F0%9F%93%8A%20VIEW%20CASE%20STUDY-111827?style=for-the-badge" />
</a>

</div>

<br/>

> **The core idea:** an API existing is not the same thing as an integration being
> easy to build. This project separates authentication, access, API surface,
> MCP availability, and practical buildability into an evidence-backed research
> pipeline.

---

## ⚡ At a Glance

| | Result |
|---|---:|
| **Applications researched** | **100 / 100** |
| **Categories covered** | **10** |
| **Evidence sources collected** | **527** |
| **Final structured records** | **100** |
| **Apps manually verified** | **10** |
| **Field-level verification checks** | **50** |
| **First-pass field accuracy** | **64.0%** |
| **Apps requiring correction** | **9 / 10** |
| **Verified field corrections applied** | **18** |

### What we found

**OAuth dominates.**  
OAuth was the most common normalized authentication pattern across the portfolio.

**API keys remain important.**  
Static credentials continue to represent a major integration path alongside OAuth.

**MCP is emerging, not universal.**  
The dataset contains official and community MCP implementations, but MCP support
remains unknown for a large share of the portfolio.

**"Has an API" ≠ "Buildable today."**  
Buildability varies substantially because permissions, plan restrictions, access
requirements, and implementation details matter.

**Verification changes the answer.**  
A 10-app verification sample produced **64% first-pass field accuracy** and
required **18 field-level corrections**.

---

# 🎯 Why This Exists

The problem is deceptively simple:

> **Research 100 applications and determine how practical they are as integration targets.**

Doing that manually is slow and difficult to scale.

Asking an LLM to answer everything directly is faster, but creates a different problem:

**hallucination, unsupported inference, inconsistent terminology, and weak provenance.**

So the system was designed around a different principle:

```text
SEARCH FIRST
     ↓
COLLECT EVIDENCE
     ↓
SYNTHESIZE WITH LOCAL LLM
     ↓
NORMALIZE
     ↓
VERIFY HIGH-RISK CLAIMS
     ↓
ANALYZE PATTERNS