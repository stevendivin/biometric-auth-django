import numpy as np
from django.test import TestCase

from .services.matching import FACE_MATCH_THRESHOLD, VOICE_MATCH_THRESHOLD, cosine_similarity


class CosineSimilarityTests(TestCase):
    def test_identical_vectors_give_similarity_one(self):
        v = np.array([1.0, 2.0, 3.0])
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0, places=5)

    def test_orthogonal_vectors_give_similarity_zero(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        self.assertAlmostEqual(cosine_similarity(a, b), 0.0, places=5)

    def test_zero_vector_does_not_crash(self):
        a = np.zeros(5)
        b = np.ones(5)
        self.assertEqual(cosine_similarity(a, b), 0.0)

    def test_thresholds_are_sane_probabilities(self):
        self.assertTrue(0.0 < FACE_MATCH_THRESHOLD < 1.0)
        self.assertTrue(0.0 < VOICE_MATCH_THRESHOLD < 1.0)
