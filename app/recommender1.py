import json
import os
from typing import Dict, List, Tuple
from collections import Counter
import asyncio


def weightage_assigner(result: dict, user_id: int) -> Dict:
    """
    Calculates weightage scores for a user's activity
    based on their viewed and purchased categories.
    
    Enhanced version with better scoring algorithm and category analysis.
    """
    
    # Extract categories from search and purchase data
    category_list = [item.get("category", "") for item in result.get("search", []) if item.get("category")]
    product_list = [item.get("product_category", "") for item in result.get("purchase", []) if item.get("product_category")]
    
    # Handle empty data
    if not category_list and not product_list:
        return {
            "user_id": user_id,
            "weightage_search": 0,
            "weightage_purchase": 0,
            "overall_weight": 0,
            "search_category_unique": [],
            "search_category_duplicates": [],
            "purchase_category_unique": [],
            "purchase_category_duplicates": [],
            "top_categories": [],
            "category_scores": {}
        }
    
    # Calculate search weightage
    duplicate_searches = len(category_list) - len(set(category_list))
    unique_searches = len(set(category_list))
    weightage_search = duplicate_searches * 2 + (unique_searches / 10)
    
    # Calculate purchase weightage (purchases are more valuable)
    duplicate_purchases = len(product_list) - len(set(product_list))
    unique_purchases = len(set(product_list))
    weightage_purchase = duplicate_purchases * 3 + (unique_purchases / 10)  # Higher weight
    
    total_weight = round(weightage_search + weightage_purchase, 2)
    
    # Build unique and duplicate lists
    def split_unique_duplicates(lst: List[str]) -> Tuple[List[str], List[str]]:
        """Split list into unique and duplicate items"""
        unique = []
        duplicates = []
        seen = set()
        
        for item in lst:
            if item not in seen:
                unique.append(item)
                seen.add(item)
            else:
                duplicates.append(item)
        
        return unique, duplicates
    
    unique_categories, duplicate_categories = split_unique_duplicates(category_list)
    unique_products, duplicate_products = split_unique_duplicates(product_list)
    
    # Calculate category scores (frequency-based)
    all_categories = category_list + product_list
    category_counter = Counter(all_categories)
    
    # Score each category (purchases count more)
    category_scores = {}
    for category in set(all_categories):
        search_count = category_list.count(category)
        purchase_count = product_list.count(category)
        # Purchases weighted 3x more than searches
        score = (search_count * 1.0) + (purchase_count * 3.0)
        category_scores[category] = round(score, 2)
    
    # Get top categories by score
    top_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)[:10]
    
    result_data = {
        "user_id": user_id,
        "weightage_search": round(weightage_search, 2),
        "weightage_purchase": round(weightage_purchase, 2),
        "overall_weight": total_weight,
        "search_category_unique": unique_categories,
        "search_category_duplicates": duplicate_categories,
        "purchase_category_unique": unique_products,
        "purchase_category_duplicates": duplicate_products,
        "top_categories": [{"category": cat, "score": score} for cat, score in top_categories],
        "category_scores": category_scores,
        "total_interactions": len(category_list) + len(product_list),
        "search_count": len(category_list),
        "purchase_count": len(product_list)
    }
    
    return result_data


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
    loop = asyncio.get_event_loop()
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