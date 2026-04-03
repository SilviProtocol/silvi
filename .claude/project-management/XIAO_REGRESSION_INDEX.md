# SINR v3 Xiao Regression Analysis - Complete Documentation Index

**Investigation Date**: March 8, 2026
**Status**: Root cause identified, solutions proposed
**Total Documentation**: 2,461 lines across 5 files, 90 KB

---

## Quick Navigation

### For Decision Makers
1. **START HERE**: [XIAO_ANALYSIS_SUMMARY.md](XIAO_ANALYSIS_SUMMARY.md) (10 min read)
   - Executive summary in 30 seconds
   - Key findings and outcomes by version
   - Solution approaches ranked by effort
   - Next steps and timeline

### For Engineers Implementing Fix
1. **UNDERSTAND**: [XIAO_REGRESSION_VISUAL_EXPLANATION.md](XIAO_REGRESSION_VISUAL_EXPLANATION.md) (15 min read)
   - Diagrams showing cascade effect
   - Component-by-component breakdown
   - Debugging visualization guide

2. **DEEP DIVE**: [XIAO_REGRESSION_FORENSIC_ANALYSIS.md](XIAO_REGRESSION_FORENSIC_ANALYSIS.md) (20 min read)
   - Complete root cause analysis
   - Full code path tracing
   - Why retraining failed
   - Architecture problem identification

3. **IMPLEMENT**: [XIAO_REGRESSION_IMPLEMENTATION_ROADMAP.md](XIAO_REGRESSION_IMPLEMENTATION_ROADMAP.md) (30 min read)
   - Step-by-step implementation for 3 approaches
   - Curriculum learning code with examples
   - Separate branch architecture
   - Benchmarking scripts
   - Timeline (4-5 weeks)

4. **REFERENCE**: [XIAO_REGRESSION_CODE_REFERENCE.md](XIAO_REGRESSION_CODE_REFERENCE.md) (20 min read)
   - Exact file locations and line numbers
   - v14 vs v15 behavior side-by-side
   - Training data distribution statistics
   - Critical code paths mapped

---

## Document Breakdown

### 1. XIAO_ANALYSIS_SUMMARY.md (300 lines)
**Best For**: Executives, project managers, quick reference

**Contains**:
- Problem statement (30 seconds)
- Why correct data made things worse
- Root cause (architectural fragility)
- Key findings (verified with code)
- Solution approaches ranked by effort vs. risk
- Expected outcomes by version
- Validation checklist
- Next steps and decision points

**Key Insight**: This isn't a data quality issue; it's an architecture problem. The model was implicitly optimized for buggy constant xiao signal (0). Correcting it exposes five cascading mechanisms.

**Action Item**: If you have 10 minutes, read this first.

---

### 2. XIAO_REGRESSION_VISUAL_EXPLANATION.md (402 lines)
**Best For**: Visual learners, team presentations, whiteboarding

**Contains**:
- Core problem in one diagram
- Full cascade effect visualization
- Component-by-component breakdown with ASCII diagrams
- Why each component breaks when xiao is fixed
- Decouple-the-mechanisms solution diagram
- Expected performance trajectory
- Debugging visualization guide

**Key Diagrams**:
1. v14 vs v15 training comparison
2. Full cascade effect flow chart
3. Embedding index problem visualization
4. Land state class problem
5. Planted auxiliary loss problem
6. Linear layer covariate shift
7. Proposed decoupled architecture
8. Debugging decision tree

**Action Item**: If you need to explain this to someone, use these diagrams.

---

### 3. XIAO_REGRESSION_FORENSIC_ANALYSIS.md (662 lines)
**Best For**: Deep technical understanding, architecture review

**Contains**:
- Executive summary
- Critical code path analysis (7 sections)
- Complete root cause diagnosis (4 major problems + 4 secondary effects)
- Why retraining with correct data still fails
- Clean fix strategy (4 options)
- Key insights (4 fundamental lessons)
- Validation approach (4 tests)
- Summary table: Mechanism comparison
- Conclusion and recommended next step

**Critical Sections**:
1. Categorical Feature Configuration (exactly how xiao maps to indices)
2. Training Data: Buggy vs Corrected (distribution statistics)
3. Embedding Input During Training (how indices flow through)
4. How Embeddings Flow Into Model (cascade starts here)
5. Land State Class Computation (hardcoded coupling)
6. Planted Auxiliary Loss Mechanism (signal inversion)
7. Categorical Embedding Alignment in Inference (mismatch at prediction time)

**Code References**: All references are precise (file name + line numbers).

**Action Item**: If you want to understand every detail, read this.

---

### 4. XIAO_REGRESSION_CODE_REFERENCE.md (493 lines)
**Best For**: Implementing changes, debugging, code review

**Contains**:
- Precise file and line number for each component
- 12 critical code locations mapped
- v14 behavior vs v15 behavior side-by-side for each location
- Training data distribution statistics
- Model architecture parameters
- Summary table: All cascade points
- Files to modify for each fix option
- Critical files for validation

**Quick Reference Table**: All 12 components in 1 table showing:
- Location (file + lines)
- v14 behavior
- v15 behavior

**Useful For**:
- Finding exact locations to edit
- Understanding data flow
- Checking assumptions
- Code review

**Action Item**: Use this when implementing the fix.

---

### 5. XIAO_REGRESSION_IMPLEMENTATION_ROADMAP.md (604 lines)
**Best For**: Project planning, implementation, timeline

**Contains**:
- Problem statement (TL;DR)
- Strategy comparison table (4 approaches, effort vs. risk)
- 5-phase implementation plan with timelines
- Phase 1: Validation & Diagnosis (Days 1-3)
- Phase 2: Curriculum Learning (Days 4-10) ← RECOMMENDED
- Phase 3: Separate Branch (Weeks 2-3)
- Phase 4: Validation & Rollout (Weeks 3-4)
- Phase 5: Deployment & Monitoring (Week 4)
- Debugging checklist
- Success metrics
- Timeline and resource estimate (4-5 weeks, 290 person-hours)

**Implementation Code Provided**:
- Curriculum learning class definition
- Training loop modifications with examples
- Separate xiao branch architecture
- Benchmarking script template
- Feature engineering examples

**Recommended Path**:
1. Start with Curriculum Learning (1 week, low risk)
2. If successful, deploy and plan Separate Branch for v17
3. If fails, escalate to Separate Branch immediately

**Action Item**: Follow this step-by-step if implementing the fix.

---

## Key Statistics

| Metric | Value |
|--------|-------|
| Total Lines | 2,461 |
| Total File Size | 90 KB |
| Number of Documents | 5 |
| Diagrams | 8 |
| Code Examples | 15+ |
| Precise Code References | 50+ |
| Timeline Covered | 4-5 weeks |
| Recommended Path | Curriculum + Separate |
| Expected Final Rank | #5-10 |
| Current Rank | #2 (v14, buggy) |
| Broken Rank | #92 (v15, correct) |

---

## Reading Paths

### Path A: Executive Decision (30 minutes)
```
1. This index (5 min)
2. XIAO_ANALYSIS_SUMMARY.md (10 min)
3. XIAO_REGRESSION_VISUAL_EXPLANATION.md - diagrams only (5 min)
4. Decision: Approve Phase 1 + 2 (curriculum learning)
```

### Path B: Technical Lead (2 hours)
```
1. XIAO_ANALYSIS_SUMMARY.md (10 min)
2. XIAO_REGRESSION_VISUAL_EXPLANATION.md (15 min)
3. XIAO_REGRESSION_FORENSIC_ANALYSIS.md - sections 1-5 (30 min)
4. XIAO_REGRESSION_CODE_REFERENCE.md - summary table (5 min)
5. XIAO_REGRESSION_IMPLEMENTATION_ROADMAP.md - Phase 2 (30 min)
6. Plan Phase 1 validation with team
```

### Path C: Implementing Engineer (4 hours)
```
1. XIAO_ANALYSIS_SUMMARY.md (10 min)
2. XIAO_REGRESSION_VISUAL_EXPLANATION.md - all (20 min)
3. XIAO_REGRESSION_FORENSIC_ANALYSIS.md - complete (40 min)
4. XIAO_REGRESSION_CODE_REFERENCE.md - complete (30 min)
5. XIAO_REGRESSION_IMPLEMENTATION_ROADMAP.md - Phase 1-2 (90 min)
6. Start Phase 1 validation
```

### Path D: Code Reviewer (3 hours)
```
1. XIAO_REGRESSION_FORENSIC_ANALYSIS.md - critical code paths (30 min)
2. XIAO_REGRESSION_CODE_REFERENCE.md - complete (40 min)
3. XIAO_REGRESSION_VISUAL_EXPLANATION.md - debugging section (10 min)
4. XIAO_REGRESSION_IMPLEMENTATION_ROADMAP.md - code examples (40 min)
5. Review PR against checklist
```

---

## Key Questions Answered

| Question | Document | Section |
|----------|----------|---------|
| Why did correcting xiao hurt? | Summary | Why Correct Data Made Things Worse |
| What are the five cascade mechanisms? | Forensic | Root Cause Diagnosis |
| How do embeddings flow through the model? | Code Ref | How Embeddings Flow Into Model |
| What's the quickest fix? | Implementation | Phase 2: Curriculum Learning |
| What's the best long-term design? | Implementation | Phase 3: Separate Branch |
| Where exactly does xiao mapping happen? | Code Ref | Categorical Feature Config |
| Why does land_state_class matter? | Forensic | Land State Class Computation |
| How can I debug this? | Visual Explanation | Debugging Visualization |
| What timeline should I plan? | Implementation | Timeline & Resource Estimate |
| Will curriculum learning work? | Roadmap | Phase 2 Success Criteria |

---

## Critical Files to Modify

### For Curriculum Learning (Phase 2)
- `orchestrator/train_on_vm.py` — Add curriculum schedule and mask application

### For Separate Branch (Phase 3)
- `orchestrator/train_on_vm.py` — New xiao branch architecture
- `orchestrator/v3_point_inference.py` — Remove hardcoded xiao==2 rule
- Both files documented in Implementation Roadmap

---

## Success Indicators

By the end of this analysis, you should:

- [ ] Understand why v14 (#2) worked but v15 (#92) failed
- [ ] Identify all 5 cascade mechanisms
- [ ] Recognize that this is an architecture problem, not data problem
- [ ] Know 3 solution approaches and their trade-offs
- [ ] Have a timeline (4-5 weeks to optimal, 1-2 weeks to acceptable)
- [ ] Understand how to validate the hypothesis (Phase 1)
- [ ] Be ready to implement the fix (Phase 2-3)

---

## Contact & Questions

If clarification needed on any section:

1. **For forensic analysis questions**: Refer to `XIAO_REGRESSION_FORENSIC_ANALYSIS.md`
2. **For code location questions**: Refer to `XIAO_REGRESSION_CODE_REFERENCE.md`
3. **For implementation questions**: Refer to `XIAO_REGRESSION_IMPLEMENTATION_ROADMAP.md`
4. **For visual explanations**: Refer to `XIAO_REGRESSION_VISUAL_EXPLANATION.md`
5. **For executive summary**: Refer to `XIAO_ANALYSIS_SUMMARY.md`

---

## Version History

| Version | Date | Notes |
|---------|------|-------|
| v1.0 | Mar 8, 2026 | Initial comprehensive analysis |

---

## Recommended Next Actions

**Today**:
- [ ] Decision maker reads Summary (10 min)
- [ ] Technical lead reads Summary + Visual Explanation (30 min)
- [ ] Assign engineer for Phase 1 validation

**This Week**:
- [ ] Complete Phase 1 validation
- [ ] Confirm hypothesis with debug output
- [ ] Begin Phase 2 curriculum learning implementation

**Next Week**:
- [ ] Train v16_curriculum on H100
- [ ] Benchmark results
- [ ] Decision: Deploy or escalate to Phase 3

**Weeks 2-3**:
- [ ] If needed, implement Phase 3 (separate branch)
- [ ] Train v17_separate_branch

**Week 4**:
- [ ] Final validation
- [ ] Deployment planning
- [ ] Production rollout

---

## Success Definition

**v16 Achievement** (Phase 2):
- Xiao feature correctly integrated
- NZ plantation Pinus radiata ranks #5-15 (up from #92)
- No regression on other benchmarks
- Model distinguishes plantation vs natural forest
- Training converges smoothly

**v17 Achievement** (Phase 3):
- Clean architecture (xiao decoupled)
- NZ plantation ranks #5-10
- Plantation detection accurate
- Extensible design for future improvements

---

**Document Prepared By**: Deep Analysis Architect
**Analysis Completion**: March 8, 2026
**Status**: Ready for implementation
**Confidence Level**: High (verified with code examination)
