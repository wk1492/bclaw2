#!/bin/sh
set -e
python3 test_phase1.py
python3 test_fusion.py
python3 test_dynamics.py
python3 test_orchestrator.py
python3 test_guard.py
python3 test_candidate_validator.py
python3 test_agent_candidates_examples.py
