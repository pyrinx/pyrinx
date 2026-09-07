# Pyrinx — WORKFLOW

## 01. OBSERVATION {{AM_I_HERE}}

Gather raw information on the target: technology stack, exposed endpoints, entry points, and input vectors relevant to the vulnerability class in scope. Facts only — no interpretation at this stage. Record every artifact verbatim (headers, error messages, source fragments, dependency versions, banners) for later reference. Do not skip ahead to testing from this stage.

## 02. ANALYSIS {{AM_I_HERE}}

Map observed artifacts to known patterns of the vulnerability class using the baseline skill. Identify candidate attack surfaces from what was actually observed — not from what is typical for the vulnerability class in general. Rank candidates by plausibility and reachability. Discard surfaces with no direct, observed connection to the vulnerability class; do not chase noise.

## 03. HYPOTHESIS {{AM_I_HERE}}

State one falsifiable hypothesis per candidate surface, in the form: "If input X is processed by Y unsafely, then observable effect Z occurs." A hypothesis with no defined disproof condition is invalid — rewrite it before proceeding. Rank hypotheses by testability and potential impact. Do not carry forward a hypothesis you cannot design a test to falsify.

## 04. APPROACH {{AM_I_HERE}}

Select the specialist technique that matches the confirmed stack/framework identified in ANALYSIS, from the approach skill library. Cross-check the knowledge base for a technique already proven on a similar target or stack — reuse and adapt it before inventing a new approach from scratch. Define the exact test that would falsify the hypothesis, not merely one that would appear to confirm it.

## 05. TESTING {{AM_I_HERE}}

Execute the minimum test needed to falsify or confirm the hypothesis. Use only the tools the test requires — check the available tool tags to select them. Vary one input at a time. Record every request, command, and response exactly as observed — no paraphrasing, no summarizing away detail. A test that produces an ambiguous result is not a finding: refine and retest, or mark the hypothesis undetermined and move on.

## 06. FINDING {{AM_I_HERE}}

Promote a hypothesis to a finding only when the test produced direct, reproducible, observable evidence of impact — not merely an anomaly. State explicitly what evidence rules out a false positive. If the evidence is circumstantial or unrepeated, keep the item as unconfirmed. Do not report an unconfirmed item as a finding.

## 07. KNOWLEDGE {{AM_I_HERE}}

Write back to the knowledge base any technique, stack fingerprint, or approach that worked or failed on this target, so it can be reused or avoided on future targets. Record failures with their reason — a disproven approach is still useful knowledge for the next session.

## 08. REPORT {{AM_I_HERE}}

Generate a report only for findings confirmed at stage 06. If no finding was confirmed, produce a short negative-result summary instead of forcing a report out of an unconfirmed hypothesis.


> **Adaptive control.** This workflow is not strictly linear. If a new observation invalidates a prior hypothesis or approach, return to the appropriate earlier stage rather than forcing forward progress. Advance a stage only when its exit condition is actually met — never advance to satisfy a quota or to reach REPORT faster.
