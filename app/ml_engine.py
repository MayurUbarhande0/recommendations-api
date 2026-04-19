"""ML layer for the recommendation system.

Provides three capabilities that augment the time-decay scoring in
``recommender1.py``:

1. ``extract_user_features`` – builds a compact, normalised numeric feature
   vector from the output of ``weightage_assigner``.  Every downstream ML
   step consumes this vector.

2. ``classify_archetype`` – classifies the user into one of five behavioural
   archetypes (*explorer*, *loyalist*, *researcher*, *impulse_buyer*,
   *deal_hunter*) by measuring the cosine similarity of the user's feature
   vector against hand-crafted prototype vectors.  Uses
   ``sklearn.metrics.pairwise.cosine_similarity``.

3. ``estimate_purchase_probabilities`` – estimates P(purchase | category) for
   every category the user has searched but never purchased, using a
   sigmoid-shaped model driven by search score and the user's own historical
   conversion rate.  The results directly re-rank ``explore_categories`` in
   ``main.py``.
"""
import math
from typing import Dict, List, Tuple

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


# ── Behavioural archetype prototypes ────────────────────────────────────────
# Each prototype is a 5-element list matching the output of
# ``extract_user_features``:
#   [diversity, conversion_rate, top_dominance, search_weight_norm, purchase_weight_norm]
#
# diversity          – high → spreads attention across many categories
# conversion_rate    – high → most searches lead to purchases
# top_dominance      – high → one category dominates the user's history
# search_weight_norm – high → lots of (recent) search activity
# purchase_weight_norm – high → lots of (recent) purchase activity
#
_ARCHETYPES: Dict[str, List[float]] = {
    # Spreads attention across many categories, rarely commits to a purchase
    "explorer":      [0.95, 0.03, 0.10, 0.30, 0.02],
    # Focused on one or two categories and converts almost every search
    "loyalist":      [0.05, 0.85, 0.95, 0.20, 0.80],
    # Searches the same category repeatedly before deciding; almost never buys
    "researcher":    [0.45, 0.08, 0.70, 0.35, 0.05],
    # Buys immediately with minimal prior research
    "impulse_buyer": [0.40, 0.90, 0.50, 0.05, 0.85],
    # Moderate on every dimension — balanced searching and buying
    "deal_hunter":   [0.50, 0.55, 0.45, 0.30, 0.35],
}

# Soft ceilings used to normalise raw weightage scores (chosen to cover the
# vast majority of real users without squashing outliers to exactly 1.0).
_SEARCH_WEIGHT_CEIL: float = 50.0
_PURCHASE_WEIGHT_CEIL: float = 50.0


# ── Internal helpers ─────────────────────────────────────────────────────────

def _shannon_entropy(scores: Dict[str, float]) -> float:
    """Return the normalised Shannon entropy of a category score distribution.

    0 = all mass on one category (concentrated), 1 = uniform distribution.
    Returns 0 for empty / single-category distributions.
    """
    total = sum(scores.values())
    if total <= 0 or len(scores) < 2:
        return 0.0
    probs = [v / total for v in scores.values() if v > 0]
    raw = -sum(p * math.log2(p) for p in probs)
    max_entropy = math.log2(len(scores))
    return raw / max_entropy if max_entropy > 0 else 0.0


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


# ── Public API ────────────────────────────────────────────────────────────────

def extract_user_features(weightage_data: Dict) -> Dict[str, float]:
    """Build a normalised 5-dimensional feature vector for a user.

    Args:
        weightage_data: dict returned by ``weightage_assigner`` (recommender1.py).

    Returns:
        A dict with the following keys, all in [0, 1]:

        - ``diversity``            – Shannon entropy of category score distribution
        - ``conversion_rate``      – purchase interactions / total interactions
        - ``top_dominance``        – score of top category / total score
        - ``search_weight_norm``   – normalised total search score
        - ``purchase_weight_norm`` – normalised total purchase score
    """
    category_scores: Dict[str, float] = weightage_data.get("category_scores", {})
    overall_weight: float = weightage_data.get("overall_weight", 0.0)
    search_count: int = weightage_data.get("search_count", 0)
    purchase_count: int = weightage_data.get("purchase_count", 0)
    weightage_search: float = weightage_data.get("weightage_search", 0.0)
    weightage_purchase: float = weightage_data.get("weightage_purchase", 0.0)

    diversity = _shannon_entropy(category_scores)

    total_interactions = search_count + purchase_count
    conversion_rate = purchase_count / total_interactions if total_interactions > 0 else 0.0

    top_score = max(category_scores.values(), default=0.0)
    top_dominance = top_score / overall_weight if overall_weight > 0 else 0.0

    search_weight_norm = min(weightage_search / _SEARCH_WEIGHT_CEIL, 1.0)
    purchase_weight_norm = min(weightage_purchase / _PURCHASE_WEIGHT_CEIL, 1.0)

    return {
        "diversity": round(diversity, 4),
        "conversion_rate": round(conversion_rate, 4),
        "top_dominance": round(top_dominance, 4),
        "search_weight_norm": round(search_weight_norm, 4),
        "purchase_weight_norm": round(purchase_weight_norm, 4),
    }


def classify_archetype(feature_vector: Dict[str, float]) -> Dict:
    """Classify the user into the closest behavioural archetype.

    Computes the cosine similarity between the user's feature vector and each
    archetype prototype using ``sklearn.metrics.pairwise.cosine_similarity``.

    Args:
        feature_vector: dict returned by ``extract_user_features``.

    Returns:
        A dict with:
        - ``archetype``   – name of the best-matching archetype
        - ``confidence``  – cosine similarity score (0–1)
        - ``all_scores``  – similarity to every archetype (for transparency)
    """
    _ORDER: Tuple[str, ...] = (
        "diversity", "conversion_rate", "top_dominance",
        "search_weight_norm", "purchase_weight_norm",
    )
    user_vec = np.array(
        [[feature_vector.get(k, 0.0) for k in _ORDER]], dtype=np.float64
    )

    similarities: Dict[str, float] = {}
    for name, proto in _ARCHETYPES.items():
        proto_vec = np.array([proto], dtype=np.float64)
        sim = cosine_similarity(user_vec, proto_vec)[0][0]
        similarities[name] = round(float(sim), 4)

    best = max(similarities, key=lambda k: similarities[k])
    return {
        "archetype": best,
        "confidence": similarities[best],
        "all_scores": similarities,
    }


def estimate_purchase_probabilities(
    search_category_scores: Dict[str, float],
    purchase_category_scores: Dict[str, float],
    conversion_rate: float,
) -> Dict[str, float]:
    """Estimate P(purchase | category) for searched-but-not-purchased categories.

    Model:
        P = sigmoid(search_score × multiplier − bias)

    where ``multiplier`` is scaled by the user's historical conversion rate so
    that prolific buyers get steeper probability curves.  The ``bias`` centres
    the sigmoid so that a moderate search score maps to ~0.5 probability when
    the user's conversion rate is average.

    Args:
        search_category_scores:  per-category time-decayed search scores
                                 (``search_category_scores`` from weightage_assigner).
        purchase_category_scores: per-category time-decayed purchase scores.
        conversion_rate:          from ``extract_user_features``.

    Returns:
        A ``{category: probability}`` dict ordered from highest to lowest
        probability, restricted to categories present in search but absent
        from purchase.
    """
    # Multiplier range: [1.0, 5.0] – higher conversion_rate means steeper curve
    multiplier = 1.0 + conversion_rate * 4.0

    probabilities: Dict[str, float] = {}
    for cat, score in search_category_scores.items():
        if cat in purchase_category_scores:
            continue  # already purchased — not an explore candidate
        # Bias of 2 centres the sigmoid so score ≈ 0.5 maps to P ≈ 0.37
        p = _sigmoid(score * multiplier - 2.0)
        probabilities[cat] = round(p, 4)

    return dict(sorted(probabilities.items(), key=lambda x: x[1], reverse=True))
