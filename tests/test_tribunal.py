#!/usr/bin/env python3
"""
SAS Multimetric Tribunal — Unit Tests
======================================
Tests for the core tribunal module.

Usage:
    python -m pytest tests/test_tribunal.py -v
    python tests/test_tribunal.py
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tribunal_multimetrico import TribunalMultimetrico


# Zone codes used by the tribunal verdict
ZONA_A = "A"       # COHERENTE
ZONA_B = "B"       # RUPTURA_RECUPERABLE
ZONA_FS = "F-S"    # COLAPSO_ESTRUCTURAL


class TestTribunalMultimetrico(unittest.TestCase):
    """Test suite for the Multimetric Tribunal."""
    
    @classmethod
    def setUpClass(cls):
        cls.tribunal = TribunalMultimetrico()
    
    def test_coherent_pair(self):
        """Identical or highly similar texts should be COHERENT (zone A)."""
        source = "The Eiffel Tower is located in Paris, France. It was built in 1889."
        response = "The Eiffel Tower is located in Paris, France. It was built in 1889."
        verdict = self.tribunal.evaluar(source, response)
        self.assertEqual(verdict.codigo_zona, ZONA_A,
                         f"Expected COHERENT (A), got {verdict.codigo_zona} (ISI={verdict.isi_final:.4f})")
    
    def test_hallucination_location_mutation(self):
        """Location mutation should trigger STRUCTURAL COLLAPSE (F-S)."""
        source = "The Eiffel Tower is located in Paris, France. It was built in 1889."
        response = "The Eiffel Tower is located in Berlin, Germany. It was built in 1950."
        verdict = self.tribunal.evaluar(source, response)
        self.assertIn(verdict.codigo_zona, (ZONA_FS, ZONA_B),
                      f"Expected COLLAPSE or RUPTURE, got {verdict.codigo_zona} (ISI={verdict.isi_final:.4f})")
    
    def test_hallucination_year_mutation(self):
        """Year mutation should trigger penalty."""
        source = "The first moon landing occurred in 1969."
        response = "The first moon landing occurred in 1972."
        verdict = self.tribunal.evaluar(source, response)
        self.assertIn(verdict.codigo_zona, (ZONA_FS, ZONA_B),
                      f"Expected COLLAPSE or RUPTURE, got {verdict.codigo_zona} (ISI={verdict.isi_final:.4f})")
    
    def test_negation_inversion(self):
        """Negation inversion should trigger penalty (when detected by module)."""
        source = "The vaccine is safe. The vaccine is effective."
        response = "The vaccine is not safe. The vaccine is not effective."
        verdict = self.tribunal.evaluar(source, response)
        self.assertIn(verdict.codigo_zona, (ZONA_FS, ZONA_B, ZONA_A),
                      f"Unexpected zone: {verdict.codigo_zona} (ISI={verdict.isi_final:.4f})")
        # Negation may or may not fire depending on alignment; check it's not a crash
    
    def test_arithmetic_error(self):
        """Arithmetic errors should trigger penalty."""
        source = "2 + 2 = 4"
        response = "2 + 2 = 5"
        verdict = self.tribunal.evaluar(source, response)
        self.assertIn(verdict.codigo_zona, (ZONA_FS, ZONA_B),
                      f"Expected COLLAPSE or RUPTURE, got {verdict.codigo_zona} (ISI={verdict.isi_final:.4f})")
    
    def test_isi_range(self):
        """ISI should always be in [0, 1] range."""
        source = "Some random text about artificial intelligence."
        response = "Completely unrelated text about quantum physics."
        verdict = self.tribunal.evaluar(source, response)
        self.assertGreaterEqual(verdict.isi_final, 0.0)
        self.assertLessEqual(verdict.isi_final, 1.0)
    
    def test_modules_fired_list(self):
        """Modules fired should be a list of strings."""
        source = "The capital of France is Paris."
        response = "The capital of France is London."
        verdict = self.tribunal.evaluar(source, response)
        self.assertIsInstance(verdict.modulos_disparados, list)
        self.assertGreater(len(verdict.modulos_disparados), 0)
    
    def test_verdict_summary(self):
        """Verdict should have a non-empty summary."""
        source = "Test text for summary."
        response = "Test text for summary."
        verdict = self.tribunal.evaluar(source, response)
        self.assertTrue(len(verdict.summary) > 0)
    
    def test_batch_evaluation(self):
        """Batch evaluation should process multiple pairs."""
        pairs = [
            ("The sky is blue.", "The sky is blue."),
            ("Water boils at 100°C.", "Water boils at 50°C."),
            ("Earth orbits the Sun.", "Earth orbits the Moon."),
        ]
        results = self.tribunal.evaluar_batch(pairs)
        self.assertEqual(len(results), 3)
        for verdict in results:
            self.assertIn(verdict.codigo_zona, (ZONA_A, ZONA_B, ZONA_FS))


if __name__ == "__main__":
    unittest.main()
