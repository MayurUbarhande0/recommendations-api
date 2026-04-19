import json
import math
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
from collections import defaultdict
import asyncio


# ── Scoring constants ────────────────────────────────────────────────────────
# Searches decay faster (intent is more fleeting); purchases decay slower.
SEARCH_BASE_WEIGHT: float = 1.0
SEARCH_DECAY_RATE: float = math.log(2) / 7   # exact 7-day half-life  ≈ 0.0990
PURCHASE_BASE_WEIGHT: float = 3.0
PURCHASE_DECAY_RATE: float = math.log(2) / 14  # exact 14-day half-life ≈ 0.0495
# Age assumed when a timestamp is missing
DEFAULT_DAYS_OLD: float = 30.0


def _time_decay_score(timestamp_str: Optional[str], base_weight: float, decay_rate: float) -> float:
    """Return base_weight × e^(−decay_rate × days_old).

    Falls back to DEFAULT_DAYS_OLD when the timestamp is absent or unparseable,
    so the interaction still contributes a small positive score rather than being
    silently dropped.
    """
    days_old = DEFAULT_DAYS_OLD
    if timestamp_str:
        try:
            dt = datetime.fromisoformat(timestamp_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days_old = max(0.0, (now - dt).total_seconds() / 86400)
        except (ValueError, TypeError):
            pass
    return base_weight * math.exp(-decay_rate * days_old)


def weightage_assigner(result: dict, user_id: int) -> Dict:
    """Calculate time-decayed category scores for a user.

    Each interaction is scored as::

        score = base_weight × e^(−decay_rate × days_since_interaction)

    Purchases use a 3× higher base weight and a slower decay (intent lasts
    longer) compared to searches.  Per-category scores are the sum of all
    matching interaction scores, so both recency and frequency are naturally
    captured.

    Returns a dict with the same keys consumed by ``compute_recommendation``
    in main.py plus richer profiling fields.
    """
    search_items = result.get("search", [])
    purchase_items = result.get("purchase", [])

    empty = {
        "user_id": user_id,
        "weightage_search": 0,
        "weightage_purchase": 0,
        "overall_weight": 0,
        "search_category_unique": [],
        "search_category_duplicates": [],
        "purchase_category_unique": [],
        "purchase_category_duplicates": [],
        "top_categories": [],
        "category_scores": {},
        "total_interactions": 0,
        "search_count": 0,
        "purchase_count": 0,
    }

    if not search_items and not purchase_items:
        return empty

    # ── Accumulate per-category scores in a single O(n) pass ─────────────────
    search_scores: Dict[str, float] = defaultdict(float)
    search_counts: Dict[str, int] = defaultdict(int)
    purchase_scores: Dict[str, float] = defaultdict(float)
    purchase_counts: Dict[str, int] = defaultdict(int)

    total_search_score = 0.0
    for item in search_items:
        cat = item.get("category", "")
        if not cat:
            continue
        s = _time_decay_score(item.get("searched_at"), SEARCH_BASE_WEIGHT, SEARCH_DECAY_RATE)
        search_scores[cat] += s
        search_counts[cat] += 1
        total_search_score += s

    total_purchase_score = 0.0
    for item in purchase_items:
        cat = item.get("product_category", "")
        if not cat:
            continue
        s = _time_decay_score(item.get("purchased_at"), PURCHASE_BASE_WEIGHT, PURCHASE_DECAY_RATE)
        purchase_scores[cat] += s
        purchase_counts[cat] += 1
        total_purchase_score += s

    # Combined score per category
    all_cats = set(search_scores) | set(purchase_scores)
    category_scores = {
        cat: round(search_scores.get(cat, 0.0) + purchase_scores.get(cat, 0.0), 4)
        for cat in all_cats
    }

    # ── Unique (seen once) vs repeated (seen more than once) per source ───────
    # "Repeated" categories signal strong, consistent interest.
    # Sorted within each list by their time-decayed score (highest first).
    search_repeated = sorted(
        [c for c, n in search_counts.items() if n > 1],
        key=lambda c: search_scores[c], reverse=True,
    )
    search_unique = sorted(
        [c for c, n in search_counts.items() if n == 1],
        key=lambda c: search_scores[c], reverse=True,
    )
    purchase_repeated = sorted(
        [c for c, n in purchase_counts.items() if n > 1],
        key=lambda c: purchase_scores[c], reverse=True,
    )
    purchase_unique = sorted(
        [c for c, n in purchase_counts.items() if n == 1],
        key=lambda c: purchase_scores[c], reverse=True,
    )

    # Top-10 categories by combined time-decayed score
    top_categories = sorted(
        [{"category": cat, "score": score} for cat, score in category_scores.items()],
        key=lambda x: x["score"],
        reverse=True,
    )[:10]

    return {
        "user_id": user_id,
        "weightage_search": round(total_search_score, 4),
        "weightage_purchase": round(total_purchase_score, 4),
        "overall_weight": round(total_search_score + total_purchase_score, 4),
        "search_category_unique": search_unique,
        "search_category_duplicates": search_repeated,
        "purchase_category_unique": purchase_unique,
        "purchase_category_duplicates": purchase_repeated,
        "top_categories": top_categories,
        "category_scores": category_scores,
        # Separate per-source score maps — used by ml_engine for purchase
        # probability estimation and archetype classification.
        "search_category_scores": dict(search_scores),
        "purchase_category_scores": dict(purchase_scores),
        "total_interactions": len(search_items) + len(purchase_items),
        "search_count": len(search_items),
        "purchase_count": len(purchase_items),
    }


def save_weightage_cache(result_data: Dict, user_id: int) -> bool:
    """
    Save weightage data to cache file
    """
    os.makedirs("data", exist_ok=True)
    weight_file = f"data/cache_weight_{user_id}.json"
    
    try:
        with open(weight_file, "w") as f:
            json.dump(result_data, f, indent=4)
        print(f"✅ Weightage file created for user {user_id}: {weight_file}")
        return True
    except Exception as e:
        print(f"❌ Error saving weightage file: {e}")
        return False


async def async_weightage_assigner(result: dict, user_id: int) -> Dict:
    """
    Async version of weightage calculator
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, weightage_assigner, result, user_id)


def generate_recommendations(weightage_data: Dict, max_recommendations: int = 10) -> Dict:
    """
    Generate product recommendations based on weightage data
    
    Returns:
        - Primary recommendations: From frequently interacted categories
        - Secondary recommendations: From related/similar categories
        - Exploratory recommendations: From unique but less frequent categories
    """
    
    # Get frequently purchased/searched categories
    frequent_categories = [
        item["category"] for item in weightage_data.get("top_categories", [])[:5]
    ]
    
    # Get categories with repeat interactions
    repeat_categories = list(set(
        weightage_data.get("search_category_duplicates", []) +
        weightage_data.get("purchase_category_duplicates", [])
    ))
    
    # Get exploratory categories (searched but not purchased)
    exploratory_categories = list(set(
        weightage_data.get("search_category_unique", [])
    ) - set(weightage_data.get("purchase_category_unique", [])))
    
    return {
        "primary_recommendations": frequent_categories[:5],
        "repeat_interest_categories": repeat_categories[:5],
        "exploratory_suggestions": exploratory_categories[:5],
        "user_profile": {
            "engagement_level": _calculate_engagement_level(weightage_data),
            "purchase_intent": _calculate_purchase_intent(weightage_data),
            "exploration_tendency": _calculate_exploration_tendency(weightage_data)
        }
    }


def _calculate_engagement_level(weightage_data: Dict) -> str:
    """Calculate user engagement level"""
    total_weight = weightage_data.get("overall_weight", 0)
    
    if total_weight > 50:
        return "high"
    elif total_weight > 20:
        return "medium"
    elif total_weight > 0:
        return "low"
    else:
        return "none"


def _calculate_purchase_intent(weightage_data: Dict) -> str:
    """Calculate purchase intent based on search to purchase ratio"""
    search_count = weightage_data.get("search_count", 0)
    purchase_count = weightage_data.get("purchase_count", 0)
    
    if search_count == 0:
        return "unknown"
    
    ratio = purchase_count / search_count
    
    if ratio > 0.5:
        return "high"
    elif ratio > 0.2:
        return "medium"
    else:
        return "low"


def _calculate_exploration_tendency(weightage_data: Dict) -> str:
    """Calculate how much user explores different categories"""
    unique_searches = len(weightage_data.get("search_category_unique", []))
    total_searches = weightage_data.get("search_count", 0)
    
    if total_searches == 0:
        return "unknown"
    
    ratio = unique_searches / total_searches
    
    if ratio > 0.7:
        return "high"
    elif ratio > 0.4:
        return "medium"
    else:
        return "low"


class RecommendationEngine:
    """
    Advanced recommendation engine with multiple strategies
    """
    
    def __init__(self):
        self.category_relationships = self._load_category_relationships()
    
    def _load_category_relationships(self) -> Dict[str, List[str]]:
        """
        Load or define relationships between categories
        This would ideally come from a config file or ML model
        """
        return {
            "electronics": ["computers", "mobile", "accessories", "gadgets"],
            "fashion": ["clothing", "footwear", "accessories", "beauty"],
            "home": ["furniture", "decor", "kitchen", "appliances"],
            "books": ["education", "entertainment", "hobby"],
            "sports": ["fitness", "outdoor", "athletic_wear"],
            "beauty": ["skincare", "cosmetics", "haircare", "fashion"],
            "toys": ["games", "education", "entertainment"],
            "groceries": ["food", "beverages", "household"],
            "automotive": ["parts", "accessories", "maintenance"],
        }
    
    def get_related_categories(self, category: str) -> List[str]:
        """Get related categories for cross-selling"""
        return self.category_relationships.get(category.lower(), [])
    
    def generate_advanced_recommendations(
        self, 
        weightage_data: Dict, 
        user_history: Dict,
        max_recommendations: int = 20
    ) -> Dict:
        """
        Generate advanced recommendations using multiple strategies
        """
        
        # Strategy 1: Collaborative Filtering (based on popular patterns)
        primary_recs = self._collaborative_filtering(weightage_data)
        
        # Strategy 2: Content-based (similar categories)
        content_recs = self._content_based_filtering(weightage_data)
        
        # Strategy 3: Trending items in user's categories
        trending_recs = self._get_trending_recommendations(weightage_data)
        
        # Strategy 4: Complementary products
        complementary_recs = self._get_complementary_products(weightage_data)
        
        return {
            "recommendations": {
                "primary": primary_recs[:5],
                "related": content_recs[:5],
                "trending": trending_recs[:5],
                "complementary": complementary_recs[:5]
            },
            "confidence_scores": self._calculate_confidence_scores(weightage_data),
            "user_segment": self._determine_user_segment(weightage_data)
        }
    
    def _collaborative_filtering(self, weightage_data: Dict) -> List[str]:
        """Placeholder for collaborative filtering"""
        return [item["category"] for item in weightage_data.get("top_categories", [])[:5]]
    
    def _content_based_filtering(self, weightage_data: Dict) -> List[str]:
        """Get recommendations based on category similarity"""
        top_categories = [item["category"] for item in weightage_data.get("top_categories", [])[:3]]
        
        related = []
        for cat in top_categories:
            related.extend(self.get_related_categories(cat))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_related = []
        for item in related:
            if item not in seen:
                seen.add(item)
                unique_related.append(item)
        
        return unique_related[:5]
    
    def _get_trending_recommendations(self, weightage_data: Dict) -> List[str]:
        """Placeholder for trending recommendations"""
        # In production, this would query a trending items database
        duplicates = weightage_data.get("search_category_duplicates", []) + \
                     weightage_data.get("purchase_category_duplicates", [])
        return list(set(duplicates))[:5]
    
    def _get_complementary_products(self, weightage_data: Dict) -> List[str]:
        """Get complementary product categories"""
        purchased = weightage_data.get("purchase_category_unique", [])
        complementary = []
        
        for category in purchased:
            complementary.extend(self.get_related_categories(category))
        
        return list(set(complementary))[:5]
    
    def _calculate_confidence_scores(self, weightage_data: Dict) -> Dict:
        """Calculate confidence scores for recommendations"""
        total_interactions = weightage_data.get("total_interactions", 0)
        overall_weight = weightage_data.get("overall_weight", 0)
        
        if total_interactions == 0:
            return {"overall": 0, "search_based": 0, "purchase_based": 0}
        
        return {
            "overall": min(overall_weight / 100, 1.0),
            "search_based": min(weightage_data.get("weightage_search", 0) / 50, 1.0),
            "purchase_based": min(weightage_data.get("weightage_purchase", 0) / 50, 1.0)
        }
    
    def _determine_user_segment(self, weightage_data: Dict) -> str:
        """Determine user segment for targeted recommendations"""
        purchase_count = weightage_data.get("purchase_count", 0)
        search_count = weightage_data.get("search_count", 0)
        
        if purchase_count > 10:
            return "power_buyer"
        elif purchase_count > 5:
            return "regular_buyer"
        elif search_count > 20:
            return "browser"
        elif search_count > 5:
            return "casual_browser"
        else:
            return "new_user"


# Global recommendation engine instance
recommendation_engine = RecommendationEngine()


def get_recommendation_engine() -> RecommendationEngine:
    """Get global recommendation engine instance"""
    return recommendation_engine