"""Sanity tests for the retrieval experiment's search code. No API calls, fake vectors only."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # pre_build_research/
from retrieval_test import EMBEDDING_MODEL, key, normalize_rows, theme_hit, top_k


def test_normalize_gives_length_one():
    m = normalize_rows(np.array([[3.0, 4.0], [1.0, 0.0]]))
    assert np.allclose(np.linalg.norm(m, axis=1), 1.0)
    assert np.allclose(m[0], [0.6, 0.8])


def test_top_k_ranks_most_similar_first():
    corpus = normalize_rows(np.array([
        [1.0, 0.0, 0.0],      # row 0: points along x
        [0.0, 1.0, 0.0],      # row 1: points along y
        [0.9, 0.1, 0.0],      # row 2: almost along x
    ]))
    query = normalize_rows(np.array([1.0, 0.05, 0.0]))
    ranked = top_k(corpus, query, k=3)
    assert [i for i, _ in ranked] == [0, 2, 1]
    assert ranked[0][1] > ranked[1][1] > ranked[2][1]


def test_top_k_identical_vector_scores_one():
    corpus = normalize_rows(np.random.default_rng(0).normal(size=(50, 8)))
    (best, score), = top_k(corpus, corpus[17], k=1)
    assert best == 17 and abs(score - 1.0) < 1e-6


def test_top_k_respects_k():
    corpus = normalize_rows(np.eye(10))
    assert len(top_k(corpus, corpus[0], k=5)) == 5


def test_fingerprint_is_stable_and_specific():
    assert key("A fork attacks two pieces") == key("A fork attacks two pieces")
    assert key("A fork attacks two pieces") != key("A fork attacks two pieces.")
    assert len(key("x")) == 64
    assert EMBEDDING_MODEL in "text-embedding-3-small"          # key includes the model name


def test_theme_keywords():
    assert theme_hit("fork", "The knight forks king and rook")
    assert theme_hit("pin", "The bishop is pinned to the queen")
    assert not theme_hit("pin", "He took a pinch of salt")
    assert theme_hit("discoveredAttack", "A discovered attack wins the queen")
    assert not theme_hit("discoveredAttack", "It was discovered that the move fails")
    assert theme_hit("hangingPiece", "The bishop on c4 is hanging")
    assert theme_hit("backRankMate", "Weak back rank: Re8 is mate")
    assert theme_hit("exposedKing", "White starts a king hunt")
    assert not theme_hit("exposedKing", "The bishop controls the diagonal")
    assert theme_hit("advancedPawn", "The passed pawn will promote")
