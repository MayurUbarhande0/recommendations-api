"""
Database operations with CORRECT column names
In your schema: id column = user_id
"""
import aiomysql
from typing import List, Dict

async def get_search_data(user_id: int, pool: aiomysql.Pool) -> List[Dict]:
    """
    Fetch search data for a user
    user_id maps to 'id' column in searches table
    """
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            query = """
                SELECT 
                    id,
                    search,
                    searched_at,
                    category,
                    SUCCESS
                FROM searches 
                WHERE id = %s 
                ORDER BY searched_at DESC 
                LIMIT 100
            """
            await cur.execute(query, (user_id,))
            results = await cur.fetchall()
            
            # Convert datetime objects to strings for JSON serialization
            data = []
            for row in results:
                row_dict = dict(row)
                if 'searched_at' in row_dict and row_dict['searched_at']:
                    row_dict['searched_at'] = row_dict['searched_at'].isoformat()
                data.append(row_dict)
            
            return data


async def get_recent_purchased(user_id: int, pool: aiomysql.Pool) -> List[Dict]:
    """
    Fetch purchase data for a user
    user_id maps to 'id' column in purchase table
    """
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            query = """
                SELECT 
                    id,
                    product_name,
                    purchased_at,
                    product_category,
                    SUCCESS
                FROM purchase 
                WHERE id = %s 
                ORDER BY purchased_at DESC 
                LIMIT 100
            """
            await cur.execute(query, (user_id,))
            results = await cur.fetchall()
            
            # Convert datetime objects to strings for JSON serialization
            data = []
            for row in results:
                row_dict = dict(row)
                if 'purchased_at' in row_dict and row_dict['purchased_at']:
                    row_dict['purchased_at'] = row_dict['purchased_at'].isoformat()
                data.append(row_dict)
            
            return data