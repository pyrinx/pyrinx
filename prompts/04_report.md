# Pyrinx — REPORT

Generate this report only after a finding has reached the FINDING stage with confirmed, reproducible evidence. Follow the structure below exactly — 7 sections, in this order. No section may contain an unverified claim; if evidence for a section is incomplete, state that explicitly rather than filling the gap with assumption.

## 1. Title

One line. Format: `[VULN_CLASS] — short description — target/component`. No severity adjectives ("critical", "severe", "catastrophic") in the title — severity belongs in Impact, not asserted upfront.

## 2. Summary

2–4 sentences: what the vulnerability is, where it was found, and the direct consequence if exploited. Nothing beyond what TESTING actually confirmed.

## 3. Affected Target

Exact scope: host/endpoint/component, version or commit if known, and the authorization basis (which engagement or program this falls under). Nothing outside the defined scope may appear here.

## 4. Vulnerability Details

Root cause in technical terms: what is unsafe, why, and the mechanism of exploitation. Reference the technique used from the approach skill. Every stated assumption must trace back to an artifact from OBSERVATION or ANALYSIS — no unsourced claims.

## 5. Reproduction

Numbered, exact, minimal steps from a neutral starting state. Every step must match what was actually executed during TESTING — no cleanup or simplification that changes the outcome. A third party must be able to follow these steps and get the same result.

## 6. Evidence

Raw artifacts only: request/response pairs, command output, log excerpts — captured exactly as observed, redacted only to remove third-party data not needed to prove the finding. Every evidence item must map to a specific Reproduction step.

## 7. Impact

Concrete, bounded consequence — what an attacker could actually do, not the worst theoretical case. State the confidence level and any preconditions required (authentication level, network position, user interaction). Never inflate severity beyond what Evidence supports.
