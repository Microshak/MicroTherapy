# PRD-11: MicroTherapy — OKF Knowledge Structure

**Status:** Implemented
**Date:** 2026-07-25
**Depends on:** PRD-10 (architecture)
**Read after:** PRD-12 (router & orchestrator)

---

## 1. Objective

Define the OKF bundle layouts that make MicroTherapy stateful. Every piece of
persistent information — client profiles, treatment plans, session history,
topic knowledge, modality reference — lives in OKF-formatted markdown files.

These files ARE the database. The orchestrator skill reads them at session
start and writes them at session end.

---

## 2. Bundle Topology

```
knowledge/                          ← Root OKF bundle (may be a git repo)
│
├── index.md                        ← Bundle root index (optional frontmatter with okf_version)
├── log.md                          ← Global change history
│
├── clients/                        ← One subdirectory per client
│   ├── index.md                    ← Client directory listing
│   └── {client-id}/                ← e.g., "alice", "bob" — use first name or pseudonym
│       ├── index.md                ← Bundle index for this client
│       ├── profile.md              ← Type: ClientProfile
│       ├── history.md              ← Type: SessionHistory
│       ├── plan.md                 ← Type: TreatmentPlan
│       └── log.md                  ← Per-client change history
│
├── topics/                         ← Reusable therapy topic knowledge
│   ├── index.md                    ← Topic catalog
│   ├── anxiety.md                  ← Type: TherapyTopic
│   ├── depression.md
│   ├── shame.md
│   ├── relationships.md
│   ├── grief.md
│   ├── self-esteem.md
│   ├── trauma.md
│   ├── sexuality-and-identity.md   ← From the primer conversation
│   ├── neurodivergence.md
│   └── life-transitions.md
│
└── approaches/                     ← Modality reference (when to use each)
    ├── index.md                    ← Modality catalog
    ├── cbt.md                      ← Type: TherapyApproach
    ├── act.md
    ├── dbt.md
    ├── motivational-interviewing.md
    ├── sfbt.md
    ├── general-therapy.md
    └── crisis-response.md
```

---

## 3. Client Bundle Schemas

### 3.1 `profile.md` — Client Profile

The "global client info" — persistent across all sessions.

```markdown
---
type: ClientProfile
title: "{Name} — Client Profile"
client_id: "{unique-id}"
first_session: "2026-07-25"
total_sessions: 3
status: active              # active | paused | completed
---

# {Name} — Client Profile

## Demographics
- **Age / Range:** 30s
- **Gender:** Male
- **Relationship status:** Married, open marriage

## Presenting Concerns
- Sexuality exploration (men)
- Religious shame / self-acceptance
- Perfectionism (linked to work anxiety)

## Relevant Background
- **Childhood:** Parents stayed together but miserable, religious control,
  neglect, bullied by peers, constant punishment at school
- **Neurodivergence:** ADHD, time blindness
- **Coping pattern:** Built a protective "box" — suppressed authentic self
  to avoid punishment. This pattern still operates today.

## Relationship Context
- Wife is consistently supportive (2+ years)
- Client shows suspicion of acceptance ("waiting for other shoe to drop")
- Marriage is open; wife suggested he explore with men

## Therapy Preferences
- **Likes:** Conversational flow, one question at a time, gentle curiosity,
  metaphor (the "box" resonated)
- **Dislikes:** Bullet-point lists of questions, feeling interrogated,
  overly structured exercises
- **Pacing:** Slow and steady. Let him lead.

## Effective Modalities
- **General Therapy:** Strong rapport building, validation works well
- (Others TBD as sessions progress)

## Ineffective Modalities
- (TBD)

## Sensitive Areas
- Religious shame — approach gently, don't challenge beliefs directly
- Neurodivergence — acknowledge, don't minimize
- Family stability — deeply valued, don't threaten this

## Strengths
- Self-aware and reflective
- Willing to be vulnerable (cried during disclosure to wife)
- Committed to growth (engaging in therapy)
- Values stability and family

## Last Updated
2026-07-25
```

**Required frontmatter fields:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `ClientProfile` |
| `title` | string | Display name |
| `client_id` | string | Unique identifier |
| `first_session` | string | ISO 8601 date of first session |
| `total_sessions` | integer | Running count |
| `status` | string | `active`, `paused`, or `completed` |

**Body sections (all optional, add as needed):**
- Demographics
- Presenting Concerns
- Relevant Background
- Relationship Context
- Therapy Preferences
- Effective Modalities
- Ineffective Modalities
- Sensitive Areas
- Strengths

---

### 3.2 `history.md` — Session History

A running log. Newest entry at top. Each session is a `##` heading.

```markdown
---
type: SessionHistory
title: "{Name} — Session History"
client_id: "{unique-id}"
---

# {Name} — Session History

## 2026-07-25 — Session #1 (Intake)

**Mood at start:** Anxious but open
**Modalities used:** General Therapy (entire session — rapport building)

### Topics Discussed
- Decision to explore dating men
- Wife's supportive response (2 years ago)
- Coming out to wife while crying (ADHD medication lowered defenses)
- Childhood: religious shame, parental neglect, bullying, constant punishment
- Built a protective "box" to survive — suppressed authentic self
- Suspicion of wife's motives ("waiting for other shoe to drop")
- Health issues currently delaying action

### What Worked
- Slowing down to one question at a time (client explicitly requested this)
- Reflecting back and checking accuracy ("Am I tracking that correctly?")
- The "box" metaphor — deeply resonated
- Connecting past patterns to present behavior
- Gentle curiosity without pushing

### What Didn't
- Structured topic list at start was overwhelming (corrected immediately)
- Somatic check-ins offered but not engaged (not the right time)
- Parts work (IFS) mentioned but not pursued

### Key Insights
- Client doesn't just want to explore sexuality — he wants to discover if
  he can be his authentic self AND keep his family/stability
- The word "permission" is significant — he needed external permission to
  even consider wanting this
- Deep pattern: suppress desires to stay safe. This kept him alive as a kid.
  Now it may be keeping him from living fully.

### Plan for Next Session
- Continue Inner Landscape exploration
- Pick up at: "When health issues resolve and you could actually make a
  move — what feeling comes up most?"
- Watch for: readiness to want this for himself, not just with permission
- Consider introducing CBT if thought patterns emerge

**Mood at end:** 6/10 — relieved, felt heard
```

**Required frontmatter fields:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `SessionHistory` |
| `title` | string | Display name |
| `client_id` | string | Links to profile |

**Body convention:** Each `##` heading is a date. Sub-sections are freeform
but the following are recommended:
- Mood at start/end
- Modalities used
- Topics Discussed
- What Worked
- What Didn't
- Key Insights
- Plan for Next Session

---

### 3.3 `plan.md` — Treatment Plan

The therapist's prioritized agenda. Updated after every session.

```markdown
---
type: TreatmentPlan
title: "{Name} — Treatment Plan"
client_id: "{unique-id}"
status: active
updated: "2026-07-25"
---

# {Name} — Treatment Plan

## Priority Queue

### 1. Sexuality Exploration & Self-Discovery (Priority: HIGH)
- **Status:** Early exploration
- **Modality:** General Therapy (building safety first)
- **Future modalities:** CBT (thoughts about self), ACT (acceptance, values)
- **Last worked on:** 2026-07-25 (Session #1)
- **Progress:** Opened up significantly. Strong rapport established.
- **Next step:** Explore readiness — when health issues resolve, what comes up?

### 2. Religious Shame & Self-Acceptance (Priority: HIGH)
- **Status:** Identified but not yet directly addressed
- **Modality:** ACT (acceptance) or CBT (examine shame-based beliefs)
- **Linked to:** Issue #1 — shame is a barrier to exploration
- **Note:** Approach gently. Don't challenge faith directly. Focus on
  separating religious tradition from self-worth.

### 3. Trust & Suspicion Patterns (Priority: MEDIUM)
- **Status:** Identified
- **Modality:** CBT (examining evidence for/against suspicion)
- **Evidence gathered:** Wife has been consistently supportive for 2+ years
- **Childhood pattern:** People who should help = sources of pain
- **Note:** Don't push. Let him discover the pattern himself.

### 4. Neurodivergence & Self-Image (Priority: MONITORING)
- **Status:** Acknowledged, colors everything but not primary focus
- **Note:** Validate experiences. Don't make this "a problem to fix."

---

## This Session's Plan (auto-generated)

- [x] Build rapport, establish safety
- [x] Explore Inner Landscape cluster (sexuality, identity, "why now")
- [ ] Pick up: readiness to act when health allows
- [ ] If appropriate: gently explore the "permission" theme

## Client's Agenda (filled at session start)
- [x] Wanted to talk about dating men — addressed
- [ ] (Nothing else raised — followed therapist's plan after opening)
```

**Required frontmatter fields:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `TreatmentPlan` |
| `title` | string | Display name |
| `client_id` | string | Links to profile |
| `status` | string | `active`, `paused`, or `completed` |
| `updated` | string | ISO 8601 date of last update |

**Body sections:**
- **Priority Queue** — Numbered list of issues, each with status, modality, progress
- **This Session's Plan** — Auto-generated checklist from the queue
- **Client's Agenda** — What the client brought up (filled at session start)

---

## 4. Topic Knowledge Bundles (`topics/`)

Reusable knowledge about common therapy topics. These are NOT client-specific —
they're reference material the therapist draws from.

### Example: `topics/sexuality-and-identity.md`

```markdown
---
type: TherapyTopic
title: Sexuality Exploration & Identity
tags: [sexuality, identity, LGBTQ+, self-discovery, relationships]
---

# Sexuality Exploration & Identity

## Common Presentations
- Questioning orientation later in life (30s, 40s, 50s+)
- Married/partnered and discovering new attractions
- Religious background creating internal conflict
- Fear of losing existing relationship/family
- "Am I gay or bisexual?" — the label question

## Key Therapeutic Questions
- When did you first notice this attraction? Did you allow yourself to name it?
- What would exploring this mean for your sense of who you are?
- What feels like it's at stake? (Relationship? Identity? Stability?)
- If there were no consequences, what would you want?

## Common Patterns
- **Permission-seeking:** Waiting for external validation before allowing
  oneself to want something
- **The "box":** Compartmentalizing desires to maintain stability
- **Grief for lost time:** Mourning years spent not knowing/exploring
- **Religious shame:** "This part of me is wrong" vs. "This part of me is"

## Modality Guidance
| Modality | Best For |
|----------|----------|
| General Therapy | Initial disclosure, building safety |
| ACT | Acceptance of self, values clarification, reducing shame |
| CBT | Examining shame-based beliefs, challenging "should" statements |
| MI | Exploring ambivalence about taking action |

## Watch For
- Internalized homophobia/biphobia — don't challenge, explore gently
- Pressure to "pick a label" — let them define themselves
- Relationship implications — don't assume monogamy or polyamory
- Religious trauma — separate faith tradition from self-worth
```

**Topic frontmatter:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `TherapyTopic` |
| `title` | string | Topic name |
| `tags` | list | Cross-cutting categories |

---

## 5. Approach Knowledge Bundles (`approaches/`)

Reference for when and how to use each modality. These inform the router.

### Example: `approaches/cbt.md`

```markdown
---
type: TherapyApproach
title: Cognitive Behavioral Therapy (CBT)
modality: cbt
---

# Cognitive Behavioral Therapy (CBT)

## Best For
- Anxiety driven by catastrophic thinking
- Depression with negative self-talk
- Perfectionism, black-and-white thinking
- The client says: "Everyone thinks I'm...", "I'll definitely fail...",
  "I should..."

## Not Best For
- Client needs validation/rapport first → use General Therapy
- Client is emotionally flooded → use DBT distress tolerance first
- Client is ambivalent about change → use MI first
- Active crisis → Crisis Response

## Layering Rules
- **After DBT:** Once client is regulated, CBT can explore the thoughts
  behind the emotion
- **With ACT:** CBT challenges thought content; ACT changes relationship
  to thoughts. Use CBT first; if "fighting thoughts" emerges, switch to ACT
- **Before SFBT:** CBT provides insight; SFBT provides action planning

## Non-Responsiveness Indicators
- Client says "I know my thoughts are irrational but I still feel bad"
  → Switch to ACT (acceptance over challenging)
- Client can't engage in cognitive work → Switch to DBT (skills first)
  or General Therapy (validation)
- Client argues with every reframe → Switch to MI (don't persuade, explore)
```

**Approach frontmatter:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `TherapyApproach` |
| `title` | string | Approach name |
| `modality` | string | Short name matching skill name |

---

## 6. OKF Conventions for MicroTherapy

| Convention | Rule |
|------------|------|
| Client ID | First name or pseudonym, lowercase, hyphenated if needed |
| Dates | ISO 8601 format: `YYYY-MM-DD` |
| Modality names | Lowercase: `cbt`, `act`, `dbt`, `mi`, `sfbt`, `general`, `crisis` |
| Priority levels | `HIGH`, `MEDIUM`, `LOW`, `MONITORING` |
| Status values | `active`, `paused`, `completed`, `not-started`, `in-progress` |
| Session numbering | Sequential integers, starting at 1 |
| Mood ratings | Optional 0-10 scale |

---

## 7. File Creation Order

When creating a new client bundle:

1. `clients/{id}/index.md` — Bundle index
2. `clients/{id}/profile.md` — From intake conversation
3. `clients/{id}/plan.md` — Initial treatment plan
4. `clients/{id}/history.md` — Empty, first entry added after session 1
5. `clients/{id}/log.md` — Change log

When a session ends, update (in order):

1. `history.md` — Append new session entry
2. `plan.md` — Update priorities, status, next-session plan
3. `profile.md` — Update effective/ineffective modalities, total_sessions, etc.
4. `log.md` — Log the changes
