#!/usr/bin/env python3
"""
Test runner script for TierMoE test suite.
Discovers and executes all unit and integration tests under tests/.
"""

import sys
import unittest


def main():
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
