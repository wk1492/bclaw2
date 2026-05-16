# Technology

## BCLAW / BCLAW4 Relevance

Status: `VERIFIED_FROM_OPERATOR` — operator explicitly connected BCLAW4
        to this project as deterministic project memory

BCLAW4 provides:
- Append-only, hash-chained event ledger (tamper-evident session record)
- Deterministic replay: any session can be reconstructed identically
- Multi-agent communication via transcript bus (no hidden coupling)
- Canonical state derivation from transcript events
- Audit trail for every agent action and decision

For this project, BCLAW4 serves as:
- Reproducible scientific record of student performance sessions
- Multi-LLM coordination substrate (one LLM analyzes video,
  another interprets biomechanics, another generates student explanation)
- Deterministic memory across sessions without hidden model state
- Future governance overlay point (operator can inspect exactly what
  happened in any session)

## Multi-iPhone Joint Tracking

Status: `VERIFIED_FROM_OPERATOR` — capability exists or is in development
Description: Multiple iPhones used simultaneously to capture 3D joint
             positions during athletic movement (swing, pitch, sprint, etc.)
Privacy note: Data stays on-device or operator-controlled storage;
              no third-party cloud required
Open: `UNVERIFIED` — production-readiness, latency, calibration workflow

## Apple Vision Pro — Visual Feedback

Status: `VERIFIED_FROM_OPERATOR` — operator named Vision Pro as an idea
Use case: Real-time or post-session overlay of swing trajectory,
          joint angle corrections, target zones shown spatially
Consideration: Vision Pro is expensive and fragile in youth settings;
               may be demo/coach-facing rather than student-facing
Open: `UNVERIFIED` — whether any prototype or integration exists

## EEG / iMotions-Style Multimodal Learning

Status: `VERIFIED_FROM_OPERATOR` — operator referenced iMotions-style
        multimodal approach as inspiration
iMotions platform fuses: EEG, eye tracking, GSR, facial action coding,
                         biometrics into synchronized timeseries
Relevance: Measuring student attention, engagement, and cognitive load
           alongside physical performance data
Privacy/safety: EEG on minors requires parental consent; data handling
                must be carefully scoped
Open: `UNVERIFIED` — whether any EEG hardware is available or planned

## Student-Owned Performance Datasets

Status: `EXPLORATORY`
Design principle: Each student owns their longitudinal performance record.
                 Comparisons are opt-in. No public leaderboards.
                 Data is a tool for self-understanding, not gatekeeping.
Technical: Local-first storage; student-controlled export

## LLMs as Interpretation Layer

Status: `EXPLORATORY`
Role: Translate biomechanics outputs into plain-language explanations
      the student can understand and act on
Example: "Your hip rotation lagged your shoulder turn by 40ms.
          Here's a drill that targets that specific timing gap."
Constraint: LLM outputs are advisory only; not authoritative over
            coach or student judgment

## Privacy and Safety Considerations

- All data collection involving minors requires parental consent
- Biometric data (EEG, joint tracking) is sensitive — storage and
  retention policy must be defined before any pilot
- No facial recognition, no social comparison without explicit consent
- FERPA compliance required if any school partnership is involved
