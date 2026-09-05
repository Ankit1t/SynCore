"""Make the inr-x402 folder importable as the package root for tests.

Ensures `shared`, `mock_bank`, `facilitator`, `merchant`, `agent` resolve as
top-level packages regardless of where pytest is invoked from.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
