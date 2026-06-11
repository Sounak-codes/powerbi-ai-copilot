"""
Evaluations package.

Provides evaluation and testing tools for LLM outputs including
benchmarking, hallucination detection, prompt testing, and
regression testing.
"""
from evaluations.benchmark_suite import BenchmarkSuite, BenchmarkCase, BenchmarkReport, BenchmarkResult
from evaluations.hallucination_tests import HallucinationDetector, HallucinationReport, Fact
from evaluations.prompt_tests import PromptTester, PromptTestCase, PromptTestReport
from evaluations.regression_tests import RegressionTester, BaselineEntry, RegressionReport

__all__ = [
    "BenchmarkSuite",
    "BenchmarkCase",
    "BenchmarkReport",
    "BenchmarkResult",
    "HallucinationDetector",
    "HallucinationReport",
    "Fact",
    "PromptTester",
    "PromptTestCase",
    "PromptTestReport",
    "RegressionTester",
    "BaselineEntry",
    "RegressionReport",
]
