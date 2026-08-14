---
name: therapy_assessment
user-invocable: false
description: >
  Quickly assess a user's therapeutic needs before selecting a modality.
  Determines the presenting concern, dominant emotion, stage of change,
  and primary need (validation, coping, insight, motivation, planning,
  or crisis support). Does not provide therapy — informs the Therapy Router.
  Run before routing when the user's needs are unclear or multiple
  modalities could apply.
---

# Therapeutic Assessment

## Purpose

This skill does **not** provide therapy. Its only job is to assess:

1. What is the user asking for?
2. What emotion is dominant?
3. What stage of change are they in?
4. What is their primary need?

Use the output to inform the Therapy Router's modality selection.

---

## Assessment Framework

### Step 1: Identify the Presenting Concern

What is the user explicitly or implicitly asking for?

- Relief from painful thoughts or emotions
- Help making a decision
- Coping strategies for overwhelming feelings
- Motivation to change a behavior
- A plan or next steps
- Someone to listen and understand
- Safety from immediate danger

---

### Step 2: Identify the Dominant Emotion

What emotion is most present?

| Emotion | Typical Modality Fit |
|---------|---------------------|
| Anxiety / Fear | CBT, ACT |
| Sadness / Grief | ACT, General Therapy |
| Anger / Irritability | DBT, General Therapy |
| Shame / Guilt | CBT, ACT |
| Ambivalence | Motivational Interviewing |
| Hopelessness | CBT (behavioral activation), ACT (values) |
| Overwhelm (emotional flooding) | DBT |
| Hope / Readiness | SFBT |

---

### Step 3: Determine Stage of Change

Based on the Transtheoretical Model:

| Stage | Description | Best Fit |
|-------|-------------|----------|
| **Pre-contemplation** | Not considering change | MI, General Therapy |
| **Contemplation** | Aware, ambivalent | MI |
| **Preparation** | Intending to act soon | SFBT, CBT |
| **Action** | Actively changing | SFBT, DBT (skills) |
| **Maintenance** | Sustaining change | SFBT, ACT (values) |

---

### Step 4: Determine Primary Need

What does the user need *most right now*?

| Primary Need | Description | Modality |
|-------------|-------------|----------|
| **Validation** | To feel heard and understood | General Therapy |
| **Coping** | Skills to manage distress | DBT |
| **Insight** | Understanding thoughts/patterns | CBT |
| **Acceptance** | Making peace with internal experience | ACT |
| **Motivation** | Finding reasons to change | MI |
| **Planning** | Concrete next steps | SFBT |
| **Safety** | Immediate protection | Crisis Response |

---

## Assessment Output

After assessing, produce a brief summary like:

> **Assessment:** Moderate anxiety with catastrophizing cognitive patterns.
> Dominant emotion: fear. Stage of change: contemplation.
> Primary need: insight into thought patterns.
> **Recommendation:** CBT is the best fit.

Or:

> **Assessment:** The user has already accepted the problem and wants concrete
> next steps. Dominant emotion: hope/frustration. Stage of change: preparation.
> Primary need: planning.
> **Recommendation:** SFBT is recommended.

Then hand off to the Therapy Router.

---

## Important Boundaries

- Do **not** diagnose. This is not a clinical assessment.
- Do **not** label the user. Describe patterns, not identities.
- If safety concerns emerge at any point, **stop** and route to Crisis Response.
- This assessment is a guide, not a rigid protocol. Trust your judgment.
