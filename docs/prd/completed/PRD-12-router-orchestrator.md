# PRD-12: MicroTherapy — Enhanced Router & Session Orchestrator

**Status:** Implemented
**Date:** 2026-07-25
**Depends on:** PRD-10 (architecture), PRD-11 (OKF structure)

---

## 1. Objective

Define two skills that turn MicroTherapy from a set of isolated therapy
techniques into a coherent, stateful AI therapist:

1. **`therapy_router` (UPDATED)** — Enhanced from single-modality to
   multi-modality, history-aware, with non-responsiveness detection.

2. **`therapy_session` (NEW)** — The session orchestrator that ties
   everything together: load OKF → talk → route → track → save.

---

## 2. Skill: `therapy_router` (Updated)

### 2.1 What Changes

| Aspect | Old Router | Enhanced Router |
|--------|-----------|-----------------|
| Decision inputs | Presenting concern only | Concern + client history + OKF profile |
| Modality count | Picks 1, stays with it | Picks primary + optional secondary |
| History awareness | None | Reads `profile.md` effective/ineffective lists |
| Switching | Manual, reactive | Automatic via non-responsiveness detection |
| Layering | Not supported | Rules for combining modalities in one session |
| Outcome logging | None | Records what was tried and result |

### 2.2 Enhanced Routing Algorithm

```
INPUT:  user_message, client_profile (from OKF), session_context, current_modality
OUTPUT: recommended_modality (primary + optional secondary)

1. SAFETY CHECK
   IF message contains suicide, self-harm, or danger signals:
       RETURN Crisis Response (override all)

2. SESSION OPENING CHECK
   IF this is the first turn of a session:
       RETURN General Therapy (rapport first)
   IF this is within first 2-3 turns:
       RETURN General Therapy (don't rush into technique)

3. CLIENT HISTORY OVERRIDE
   READ client_profile.effective_modalities
   READ client_profile.ineffective_modalities
   READ client_profile.therapy_preferences (likes/dislikes)

   IF current issue has a known effective modality:
       Weight that modality higher
   IF current issue has a known ineffective modality:
       Exclude that modality for this issue

4. ISSUE-MODALITY MATCHING
   Match the presenting concern to the best modality:

   | Signal                              | Primary     | Secondary (if needed) |
   |-------------------------------------|-------------|----------------------|
   | Distorted thinking, catastrophizing | CBT         | ACT (if fighting thoughts) |
   | Fighting thoughts, rumination       | ACT         | CBT (if also distorted) |
   | Emotional overwhelm, dysregulation  | DBT         | General (if needs validation first) |
   | Ambivalence, "I want to but..."     | MI          | SFBT (if ready for action) |
   | Goal-oriented, wants plan           | SFBT        | CBT (if thoughts block action) |
   | Grief, sadness, need to vent        | General     | ACT (values work) |
   | Shame, self-criticism               | CBT or ACT  | General (validate first) |
   | Anger, interpersonal conflict       | DBT         | General (validate first) |

5. LAYERING RULES
   General Therapy ALWAYS opens a session (first 2-3 turns).
   After that, primary modality leads.

   Layer secondary when:
   - CBT work triggers emotional flooding → add DBT distress tolerance
   - ACT acceptance work reveals distorted thoughts → add CBT
   - SFBT planning stalls due to ambivalence → add MI
   - DBT skills work reveals shame beliefs → add CBT or ACT

   Do NOT layer more than 2 modalities in one session.
   Do NOT switch modalities mid-technique. Complete the intervention first.

6. NON-RESPONSIVENESS DETECTION
   After 3+ consecutive turns, check for:

   | Signal                         | Meaning              | Action                  |
   |--------------------------------|----------------------|-------------------------|
   | Client responses < 5 words     | Disengagement        | Ask if approach works   |
   | 3+ "I don't know" in a row     | Stuck                | Switch to lower-pressure modality |
   | Client changes topic abruptly  | Avoidance            | Follow, note, return later |
   | "This isn't helping"           | Explicit resistance  | Switch immediately      |
   | "You're not listening"         | Rupture              | Repair with General Therapy |

   IF non-responsive:
       LOG current modality as potentially ineffective for this issue
       SUGGEST switch to fallback (based on issue-modality table above)
       RETURN General Therapy for 1-2 turns to repair, then new modality

7. RETURN
   RETURN {
       primary: modality_name,
       secondary: modality_name or null,
       rationale: "CBT chosen because client shows catastrophizing pattern
                   about performance reviews. ACT available as secondary if
                   thought-challenging leads to increased struggle.",
       confidence: high | medium | low,
   }
```

### 2.3 Router Output Format

The router returns a structured recommendation that the orchestrator uses:

```yaml
routing_decision:
  primary: cbt
  secondary: null
  rationale: >
    Client shows catastrophizing pattern. CBT is the best first approach.
    Client history shows CBT was effective for anxiety in session #2.
  client_context_used:
    - effective_modalities: [cbt, general]
    - preference: conversational, not structured exercises
    - sensitive: religious shame — avoid direct belief challenges
  fallback_if_unresponsive: act
  suggested_technique: thought_record
```

---

## 3. Skill: `therapy_session` (New)

### 3.1 Purpose

The session orchestrator is the "conductor" — it manages the therapy session
lifecycle. It doesn't do therapy itself. It delegates everything.

### 3.2 Core Loop

```
SESSION START
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  1. LOAD CLIENT CONTEXT                              │
│     - Read knowledge/clients/{id}/profile.md         │
│     - Read knowledge/clients/{id}/plan.md            │
│     - Read knowledge/clients/{id}/history.md (last)  │
│     - If new client: create bundle from templates    │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  2. OPEN SESSION                                     │
│     - Greet naturally: "How are you doing this week?"│
│     - If returning client: reference last session    │
│       "Last time we talked about X. How has that     │
│        been since then?"                             │
│     - Ask if they have anything specific today       │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  3. MAIN LOOP (each user turn)                       │
│                                                      │
│  a. RECEIVE user message                             │
│  b. APPEND to in-memory session transcript           │
│  c. CALL therapy_router with:                        │
│     - user_message                                   │
│     - client_profile (from OKF)                      │
│     - session_context (current topic, modality)      │
│  d. RECEIVE routing decision                         │
│  e. DELEGATE to specialist skill                     │
│  f. RETURN response to user                          │
│  g. CHECK non-responsiveness (delegates to router)   │
│  h. If session ending: break loop                    │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  4. CLOSE SESSION                                    │
│     - Summarize key points discussed                 │
│     - "What's one thing you're taking away today?"   │
│     - Suggest homework or reflection                 │
│     - "I'll see you next time. Take care."           │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  5. SAVE TO OKF                                      │
│     - Append session entry to history.md             │
│     - Update plan.md priorities and statuses         │
│     - Update profile.md if new patterns emerged      │
│     - Update log.md with changes                     │
└─────────────────────────────────────────────────────┘
```

### 3.3 Session State (In-Memory Only)

The orchestrator holds these in memory during a session (not persisted):

```yaml
session_state:
  client_id: "alice"
  session_number: 3
  started_at: "2026-07-25T14:00:00Z"
  current_topic: "work anxiety"
  current_modality: cbt
  modality_turns: 4              # How many turns on current modality
  transcript: [...]              # Full session transcript
  non_responsive_count: 0        # Consecutive non-responsive turns
  mood_start: 4                  # Client's self-reported mood (0-10)
  mood_end: null                 # Filled at session close
  topics_covered: [...]          # List of topics discussed
  modalities_used: [...]         # List of modalities applied
```

### 3.4 New Client Onboarding

When a client has no OKF bundle yet:

```
1. CREATE knowledge/clients/{id}/ directory
2. CREATE index.md (bundle index)
3. CREATE profile.md (minimal — name, date, empty sections)
4. CREATE plan.md (empty priority queue)
5. CREATE history.md (empty)
6. CREATE log.md

7. OPEN with:
   "Hi, I'm glad you're here. Before we dive in, tell me a little
    about what brings you here today. What's been on your mind?"
8. After intake, POPULATE profile.md and plan.md from the conversation
```

### 3.5 Delegation Pattern

The orchestrator delegates to specialist skills by providing context:

```
ORCHESTRATOR → SPECIALIST SKILL

Input to specialist:
  - User's message
  - Client profile (relevant excerpts)
  - Current topic
  - What's been discussed this session so far
  - Router's suggested technique (if any)

Output from specialist:
  - Therapeutic response
  - What technique was used
  - Any observations (client seemed engaged/avoidant/etc.)
```

The orchestrator does NOT modify the specialist's response. Specialists remain
pure clinical knowledge — they don't know about routing, OKF, or session state.

### 3.6 Session End Detection

The orchestrator detects session end via:

| Signal | Action |
|--------|--------|
| User says "goodbye", "that's all", "thanks" | Close session |
| User says "I have to go" | Close session |
| Conversation naturally winds down (short responses, no new topics) | Ask "Is there anything else before we wrap up?" |
| Time limit exceeded (configurable, default 60 min) | Gentle nudge: "We've been talking for a while. Should we pick a stopping point?" |
| Crisis escalation | Follow crisis_response, do NOT close until safe |

---

## 4. File Changes Summary

### 4.1 Updated Files

| File | Change |
|------|--------|
| `.github/skills/therapy_router/SKILL.md` | Add: client history integration, multi-modality layering, non-responsiveness detection, outcome logging. Keep existing issue→modality mapping as baseline. |

### 4.2 New Files

| File | Type | Purpose |
|------|------|---------|
| `.github/skills/therapy_session/SKILL.md` | Skill | Session orchestration |
| `knowledge/` | OKF Bundle | Root knowledge directory |
| `knowledge/clients/{id}/` | OKF Bundle | One per client |
| `knowledge/topics/` | OKF Bundle | Reusable topic knowledge |
| `knowledge/approaches/` | OKF Bundle | Modality reference |

### 4.3 Unchanged Files

All specialist skills: `cbt`, `act`, `dbt`, `motivational_interviewing`, `sfbt`,
`crisis_response`, `general_therapy`, `assessment`, `okf-open-knowledge-format`.

---

## 5. Implementation Order

| Step | What | Produces |
|------|------|----------|
| 1 | Create `knowledge/` directory structure | Empty OKF bundle skeleton |
| 2 | Seed `knowledge/topics/` with topic files | Reusable therapy knowledge |
| 3 | Seed `knowledge/approaches/` with modality reference | Router reference data |
| 4 | Create client bundle from primer conversation | First real client data |
| 5 | Write `therapy_session/SKILL.md` | New orchestrator skill |
| 6 | Update `therapy_router/SKILL.md` | Enhanced router |
| 7 | Integration test: run a session with the primer data | Validation |

---

## 6. Example Session Flow (with Primer Data)

```
SESSION START
═════════════
Orchestrator loads: clients/alice/profile.md, plan.md, history.md

ORCHESTRATOR:
"Welcome back. Last time we talked, you shared a lot about your childhood
and how you learned to put yourself in a 'box' to stay safe. That really
seemed to resonate. How are you doing this week?"

CLIENT:
"I've been thinking about that box thing. It's kind of everywhere in my life."

ORCHESTRATOR → ROUTER:
"What modality for 'recognizing patterns of self-suppression'?"

ROUTER (reads profile: likes metaphor, conversational style):
→ Primary: ACT (defusion and self-as-context fit the "box" metaphor well)
→ Secondary: General Therapy (keep rapport strong)
→ Rationale: "Box" metaphor already established. ACT defusion techniques
  can help client observe the box without being trapped by it.

ORCHESTRATOR → ACT skill:
"Client says the box pattern is everywhere. Use defusion or self-as-context.
Client prefers conversational style, not structured exercises."

ACT SKILL:
"That's a really important observation. It sounds like you're noticing
that this isn't just about sexuality — the box has been a strategy you've
used in many areas. Can I ask: when you notice yourself 'in the box' now,
what does that feel like in your body? Is it tight? Heavy? Quiet?"

[... conversation continues ...]

SESSION END
═══════════
ORCHESTRATOR:
"Today we explored how the 'box' pattern shows up across your life, not just
in sexuality. You noticed it in how you hold back at work too. That's a big
connection. What's one thing you're taking away from today?"

CLIENT:
"That the box kept me safe as a kid but maybe I don't need it as much now."

ORCHESTRATOR:
"That's powerful. Let's sit with that this week. I'll see you next time."

→ Saves session to history.md
→ Updates plan.md: adds "self-suppression pattern" as cross-cutting theme
→ Updates profile.md: notes ACT defusion was effective
```
