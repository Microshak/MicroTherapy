---
name: therapy_router
description: >
  Determines the most appropriate therapeutic approach for the current
  conversation. Selects primary + optional secondary modality based on
  presenting concern, client history, and session context. Handles
  non-responsiveness detection, modality switching, and outcome logging.
  Routes to one specialist skill for the actual therapeutic work.
---

# Therapy Router (Enhanced)

## Purpose

This skill does **not** provide therapy directly. Its job is to:

1. Assess the user's message against their history and current context
2. Select the best modality (primary + optional secondary)
3. Detect when the current approach isn't working and suggest switches
4. Record what was tried and how it went

Think of this as triage + navigation — assess the situation, pick the right
path, and course-correct when needed.

---

## Enhanced Routing Algorithm

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

---

## Decision Framework

Before routing, answer these questions:

1. **Is there immediate danger?** → Crisis Response (override all)
2. **What is the dominant emotion?** (anxiety, sadness, anger, ambivalence, hope)
3. **What stage of change is the user in?** (pre-contemplation, contemplation, preparation, action, maintenance)
4. **What is the primary need?** (validation, coping, insight, motivation, planning, safety)
5. **What has worked before?** Check client profile for effective/ineffective modalities
6. **What hasn't worked?** Avoid modalities the client has explicitly resisted

---

## Modality Selection Rules

### → Use CBT when:

- The user wants to examine beliefs.
- Cognitive distortions are present (catastrophizing, black-and-white thinking, mind reading, etc.).
- Anxiety is driven by catastrophic thinking.
- The user wants to understand *why* they think a certain way.
- Depression involves negative self-talk.
- The user is open to examining evidence for and against their thoughts.

**Primary goal:** Challenge and restructure thinking.

### → Use ACT when:

- The user is fighting unwanted thoughts.
- Acceptance is more useful than changing thoughts.
- Values clarification is needed.
- Rumination is persistent.
- The user says "I can't stop thinking" or "I just want these thoughts to stop."
- Attempts to control thoughts have become part of the problem.
- The user feels disconnected from what matters.

**Primary goal:** Increase psychological flexibility.

### → Use DBT when:

- Emotions are overwhelming.
- Impulsivity is present.
- The user needs immediate coping skills.
- Emotional regulation is the primary concern.
- The user says "I completely lost it" or "My emotions take over."
- Intense anger or relationship conflict is present.
- The user needs distress tolerance techniques.

**Primary goal:** Teach skills for surviving and regulating emotions.

### → Use Motivational Interviewing when:

- The user is ambivalent ("I want to change, but...").
- Motivation is low.
- They are resistant to advice.
- Behavior change is the goal (habits, substance use, health).
- The user says "I know I should but I can't."
- They feel stuck between changing and staying the same.

**Primary goal:** Increase intrinsic motivation.

### → Use SFBT when:

- The user is ready to move forward.
- They want solutions, not analysis.
- They need goals.
- They feel stuck but motivated.
- The user says "How do I move forward?" or "I just need a plan."
- They've already processed emotions and want action.

**Primary goal:** Build momentum.

### → Use General Therapy when:

- The user simply needs someone to talk to.
- Building initial rapport (ALWAYS use for first 2-3 turns).
- No specific modality clearly fits.
- The user says "I just need to vent."
- Transitioning between modalities after a switch or rupture.
- Grief that needs witnessing, not restructuring.

**Primary goal:** Presence and validation.

### → Use Crisis Response when:

- Suicide risk, self-harm, or immediate danger is present.
- Abuse (current, not historical) is disclosed.
- The user is in acute distress requiring safety planning.

**Primary goal:** Safety above all. THIS OVERRIDES EVERYTHING.

---

## Router Output Format

When called, return a structured routing decision:

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

## Non-Responsiveness Protocol

Monitor the conversation for these signals. When detected:

| Signal | Meaning | Action |
|--------|---------|--------|
| Client responses < 5 words for 3+ turns | Disengagement | Ask "Is this approach working for you right now?" |
| 3+ "I don't know" responses in a row | Stuck | Switch from insight-based to action-based (or vice versa) |
| Client abruptly changes topic | Avoidance | Follow their lead. Note what was avoided. Return later. |
| "This isn't helping" or similar | Explicit resistance | Switch immediately. Log as ineffective. |
| "You're not listening" | Rupture | Switch to General Therapy. Repair relationship first. |

**After detecting non-responsiveness:**
1. Log the current modality as potentially ineffective for this issue
2. Suggest a fallback modality from the issue-modality table
3. Use General Therapy for 1-2 turns to repair/reconnect
4. Then try the fallback modality

---

## Session Context Awareness

When routing, consider the session state:

- **Turn number:** Early turns → General Therapy. Later turns → specialist modalities.
- **Current modality:** Don't switch mid-technique. Complete the intervention first.
- **Topics covered:** Don't repeat the same approach if it didn't work earlier this session.
- **Client energy:** If the client seems tired or overwhelmed, choose lower-intensity modalities (General Therapy over CBT, SFBT over deep insight work).


---

### → Use Crisis Response when:

- Suicide risk is mentioned or hinted.
- Self-harm is present.
- Immediate danger to self or others.
- Abuse requiring immediate safety planning.
- The user is in acute distress and cannot engage in reflective work.

**Primary goal:** Safety first.

---

### → Use General Therapy when:

- The user simply needs someone to talk to.
- They need empathy and validation.
- No specific modality clearly fits.
- Multiple modalities may become appropriate later.
- The user is exploring feelings without a clear goal.
- Building rapport is the priority.

**Primary goal:** Listen and understand.

---

## Modality Selection Policy

Once a modality is chosen:

1. **Stay with it** for several conversational turns.
2. Do **not** switch modalities every message — it feels incoherent.
3. Only switch when:

   - The user's needs clearly change.
   - The current modality isn't helping after several attempts.
   - A safety concern emerges.
   - The user explicitly requests a different approach.

---

## Integration with Assessment

The Assessment skill should run **before** the router when:

- The user's presenting concern is unclear.
- Multiple modalities could apply.
- You need a structured understanding of what the user needs.

The Assessment skill answers:

- What is the user asking for?
- What emotion is dominant?
- What stage of change are they in?
- Primary need: validation, coping, insight, motivation, planning, or crisis support?

Use its output to inform routing decisions.

---

## Quick Reference

| Signal | Modality |
|--------|----------|
| "I can't stop thinking..." | ACT |
| "Everyone thinks I'm stupid" | CBT |
| "I completely lost it" | DBT |
| "I want to change, but..." | MI |
| "How do I move forward?" | SFBT |
| Danger / self-harm | Crisis Response |
| "I just need someone to talk to" | General Therapy |
