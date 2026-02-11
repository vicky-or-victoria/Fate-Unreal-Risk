import asyncpg
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import random

# Global database pool
db_pool = None

# ============================================================================
# INITIALIZATION
# ============================================================================

async def init_db():
    """Initialize database connection pool and create all tables"""
    global db_pool
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    # Create connection pool
    db_pool = await asyncpg.create_pool(database_url, min_size=5, max_size=20)
    
    async with db_pool.acquire() as conn:
        # ====================================================================
        # CORE TABLES
        # ====================================================================
        
        # Guilds table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id BIGINT PRIMARY KEY,
                max_summons INTEGER DEFAULT 1,
                registration_role_id BIGINT,
                registration_channel_id BIGINT,
                registration_message_id BIGINT,
                battle_forum_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Users table (enhanced with economy and stats)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT,
                guild_id BIGINT,
                is_registered BOOLEAN DEFAULT FALSE,
                registered_at TIMESTAMP,
                saint_quartz INTEGER DEFAULT 100,
                summon_tickets INTEGER DEFAULT 3,
                last_daily_claim TIMESTAMP,
                battle_wins INTEGER DEFAULT 0,
                battle_losses INTEGER DEFAULT 0,
                elo_rating INTEGER DEFAULT 1000,
                total_summons INTEGER DEFAULT 0,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            )
        ''')
        
        # Summons/Servants table (enhanced with stats and leveling)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS summons (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                guild_id BIGINT,
                servant_name TEXT NOT NULL,
                servant_class TEXT NOT NULL,
                servant_rank TEXT NOT NULL,
                description TEXT,
                noble_phantasm TEXT,
                image_url TEXT,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0,
                base_attack INTEGER DEFAULT 100,
                base_defense INTEGER DEFAULT 100,
                base_hp INTEGER DEFAULT 1000,
                base_speed INTEGER DEFAULT 50,
                bonus_attack INTEGER DEFAULT 0,
                bonus_defense INTEGER DEFAULT 0,
                bonus_hp INTEGER DEFAULT 0,
                bonus_speed INTEGER DEFAULT 0,
                is_favorite BOOLEAN DEFAULT FALSE,
                total_battles INTEGER DEFAULT 0,
                battles_won INTEGER DEFAULT 0,
                summoned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_battle TIMESTAMP,
                FOREIGN KEY (user_id, guild_id) REFERENCES users(user_id, guild_id) ON DELETE CASCADE
            )
        ''')
        
        # ====================================================================
        # EQUIPMENT & ITEMS TABLES
        # ====================================================================
        
        # Items table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                item_type TEXT NOT NULL,
                rarity TEXT NOT NULL,
                stat_type TEXT,
                stat_value INTEGER,
                price INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User inventory
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                guild_id BIGINT,
                item_id INTEGER,
                quantity INTEGER DEFAULT 1,
                acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id, guild_id) REFERENCES users(user_id, guild_id) ON DELETE CASCADE,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
                UNIQUE(user_id, guild_id, item_id)
            )
        ''')
        
        # Equipped items (Command Seals/Equipment)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS equipped_items (
                id SERIAL PRIMARY KEY,
                servant_id INTEGER,
                item_id INTEGER,
                slot_type TEXT NOT NULL,
                equipped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (servant_id) REFERENCES summons(id) ON DELETE CASCADE,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
            )
        ''')
        
        # ====================================================================
        # BATTLE SYSTEM TABLES
        # ====================================================================
        
        # Battles table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS battles (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                challenger_id BIGINT,
                opponent_id BIGINT,
                challenger_servant_id INTEGER,
                opponent_servant_id INTEGER,
                winner_id BIGINT,
                battle_log TEXT,
                elo_change INTEGER,
                experience_gained INTEGER,
                forum_thread_id BIGINT,
                battle_type TEXT DEFAULT 'ranked',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
                FOREIGN KEY (challenger_servant_id) REFERENCES summons(id) ON DELETE SET NULL,
                FOREIGN KEY (opponent_servant_id) REFERENCES summons(id) ON DELETE SET NULL
            )
        ''')
        
        # ====================================================================
        # EVENTS & MISSIONS TABLES
        # ====================================================================
        
        # Daily missions
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS daily_missions (
                id SERIAL PRIMARY KEY,
                mission_type TEXT NOT NULL,
                description TEXT NOT NULL,
                requirement INTEGER NOT NULL,
                sq_reward INTEGER DEFAULT 10,
                ticket_reward INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User mission progress
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_mission_progress (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                guild_id BIGINT,
                mission_id INTEGER,
                progress INTEGER DEFAULT 0,
                completed BOOLEAN DEFAULT FALSE,
                claimed BOOLEAN DEFAULT FALSE,
                reset_date DATE DEFAULT CURRENT_DATE,
                FOREIGN KEY (user_id, guild_id) REFERENCES users(user_id, guild_id) ON DELETE CASCADE,
                FOREIGN KEY (mission_id) REFERENCES daily_missions(id) ON DELETE CASCADE,
                UNIQUE(user_id, guild_id, mission_id, reset_date)
            )
        ''')
        
        # Holy Grail War events
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS holy_grail_wars (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                name TEXT NOT NULL,
                description TEXT,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                prize_pool_sq INTEGER DEFAULT 1000,
                max_participants INTEGER DEFAULT 16,
                status TEXT DEFAULT 'upcoming',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            )
        ''')
        
        # War participants
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS war_participants (
                id SERIAL PRIMARY KEY,
                war_id INTEGER,
                user_id BIGINT,
                guild_id BIGINT,
                servant_id INTEGER,
                placement INTEGER,
                eliminated_at TIMESTAMP,
                FOREIGN KEY (war_id) REFERENCES holy_grail_wars(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id, guild_id) REFERENCES users(user_id, guild_id) ON DELETE CASCADE,
                FOREIGN KEY (servant_id) REFERENCES summons(id) ON DELETE SET NULL,
                UNIQUE(war_id, user_id, guild_id)
            )
        ''')
        
        # ====================================================================
        # COOLDOWNS TABLE
        # ====================================================================
        
        # Cooldowns
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS cooldowns (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                guild_id BIGINT,
                action_type TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id, guild_id) REFERENCES users(user_id, guild_id) ON DELETE CASCADE,
                UNIQUE(user_id, guild_id, action_type)
            )
        ''')
        
        # ====================================================================
        # ADMIN LOGS TABLE
        # ====================================================================
        
        # Admin action logs
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS admin_logs (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                admin_id BIGINT,
                action_type TEXT NOT NULL,
                target_user_id BIGINT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            )
        ''')
        
        # ====================================================================
        # INDEXES for performance
        # ====================================================================
        
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_summons_user_guild ON summons(user_id, guild_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_summons_level ON summons(level DESC)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_battles_guild ON battles(guild_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_elo ON users(elo_rating DESC)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_cooldowns_expires ON cooldowns(expires_at)')
        
        # Initialize default items if not exist
        await initialize_default_items(conn)
        await initialize_default_missions(conn)

async def initialize_default_items(conn):
    """Initialize default items in the database"""
    default_items = [
        # Attack boosters
        ("Excalibur Fragment", "A shard of the legendary sword", "weapon", "EX", "attack", 50, 500),
        ("Gae Bolg Replica", "A replica of Cu Chulainn's spear", "weapon", "S", "attack", 30, 300),
        ("Mystic Code - Combat Uniform", "Increases combat effectiveness", "mystic_code", "A", "attack", 20, 200),
        ("Reinforced Blade", "A strengthened weapon", "weapon", "B", "attack", 15, 150),
        ("Simple Sword", "A basic weapon", "weapon", "C", "attack", 10, 50),
        
        # Defense boosters
        ("Avalon Shard", "Fragment of the ultimate defense", "armor", "EX", "defense", 50, 500),
        ("Achilles Shield", "Protection of the greatest hero", "armor", "S", "defense", 30, 300),
        ("Knight's Armor", "Sturdy protective gear", "armor", "A", "defense", 20, 200),
        ("Iron Plate", "Basic protective equipment", "armor", "B", "defense", 15, 150),
        ("Leather Armor", "Simple protection", "armor", "C", "defense", 10, 50),
        
        # HP boosters
        ("Grail Essence", "Essence of the Holy Grail", "consumable", "EX", "hp", 500, 500),
        ("Phoenix Feather", "Revitalizing item", "consumable", "S", "hp", 300, 300),
        ("Healing Potion", "Restores vitality", "consumable", "A", "hp", 200, 200),
        ("Medicine", "Basic healing item", "consumable", "B", "hp", 150, 150),
        ("Herb", "Simple healing", "consumable", "C", "hp", 100, 50),
        
        # Speed boosters
        ("Quicksilver Boots", "Boots of ultimate speed", "accessory", "EX", "speed", 30, 500),
        ("Hermes Sandals", "Swift as the wind", "accessory", "S", "speed", 20, 300),
        ("Swift Boots", "Increases movement", "accessory", "A", "speed", 15, 200),
        ("Running Shoes", "Basic speed boost", "accessory", "B", "speed", 10, 150),
        ("Light Shoes", "Slightly faster", "accessory", "C", "speed", 5, 50),
        
        # Special items
        ("Command Seal", "Temporary massive power boost", "special", "EX", "attack", 100, 1000),
        ("Saint Quartz", "Can be sold for currency", "currency", "A", None, 0, 0),
        ("Mana Prism", "Valuable currency item", "currency", "B", None, 0, 0),
    ]
    
    for item_data in default_items:
        try:
            await conn.execute('''
                INSERT INTO items (name, description, item_type, rarity, stat_type, stat_value, price)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (name) DO NOTHING
            ''', *item_data)
        except:
            pass

async def initialize_default_missions(conn):
    """Initialize default daily missions"""
    default_missions = [
        ("battle", "Win 3 battles", 3, 30, 1),
        ("summon", "Summon 1 servant", 1, 20, 1),
        ("level_up", "Level up a servant", 1, 25, 0),
        ("win_streak", "Win 2 battles in a row", 2, 40, 2),
        ("use_item", "Equip an item to a servant", 1, 15, 0),
    ]
    
    for mission_data in default_missions:
        try:
            await conn.execute('''
                INSERT INTO daily_missions (mission_type, description, requirement, sq_reward, ticket_reward)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING
            ''', *mission_data)
        except:
            pass

async def close_db():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()

# ============================================================================
# GUILD FUNCTIONS
# ============================================================================

async def get_or_create_guild(guild_id: int):
    """Get or create guild in database"""
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO guilds (guild_id) 
            VALUES ($1) 
            ON CONFLICT (guild_id) DO NOTHING
        ''', guild_id)

async def get_max_summons(guild_id: int) -> int:
    """Get max summons for a guild"""
    async with db_pool.acquire() as conn:
        result = await conn.fetchval('''
            SELECT max_summons FROM guilds WHERE guild_id = $1
        ''', guild_id)
        return result if result else 1

async def set_max_summons(guild_id: int, max_summons: int):
    """Set max summons for a guild"""
    await get_or_create_guild(guild_id)
    async with db_pool.acquire() as conn:
        await conn.execute('''
            UPDATE guilds SET max_summons = $1 WHERE guild_id = $2
        ''', max_summons, guild_id)

async def set_battle_forum(guild_id: int, forum_id: int):
    """Set battle forum channel for a guild"""
    await get_or_create_guild(guild_id)
    async with db_pool.acquire() as conn:
        await conn.execute('''
            UPDATE guilds SET battle_forum_id = $1 WHERE guild_id = $2
        ''', forum_id, guild_id)

async def get_battle_forum(guild_id: int) -> Optional[int]:
    """Get battle forum channel ID"""
    async with db_pool.acquire() as conn:
        return await conn.fetchval('''
            SELECT battle_forum_id FROM guilds WHERE guild_id = $1
        ''', guild_id)

# ============================================================================
# USER FUNCTIONS
# ============================================================================

async def register_user(user_id: int, guild_id: int):
    """Register a user"""
    await get_or_create_guild(guild_id)
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO users (user_id, guild_id, is_registered, registered_at, saint_quartz, summon_tickets)
            VALUES ($1, $2, TRUE, $3, 100, 3)
            ON CONFLICT (user_id, guild_id) 
            DO UPDATE SET is_registered = TRUE, registered_at = $3
        ''', user_id, guild_id, datetime.now())

async def is_user_registered(user_id: int, guild_id: int) -> bool:
    """Check if user is registered"""
    async with db_pool.acquire() as conn:
        result = await conn.fetchval('''
            SELECT is_registered FROM users WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)
        return result if result else False

async def get_user_currency(user_id: int, guild_id: int) -> Dict[str, int]:
    """Get user's currency"""
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow('''
            SELECT saint_quartz, summon_tickets FROM users 
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)
        
        if result:
            return {"sq": result['saint_quartz'], "tickets": result['summon_tickets']}
        return {"sq": 0, "tickets": 0}

async def update_user_currency(user_id: int, guild_id: int, sq_change: int = 0, tickets_change: int = 0):
    """Update user's currency"""
    async with db_pool.acquire() as conn:
        await conn.execute('''
            UPDATE users 
            SET saint_quartz = saint_quartz + $1,
                summon_tickets = summon_tickets + $2
            WHERE user_id = $3 AND guild_id = $4
        ''', sq_change, tickets_change, user_id, guild_id)

async def claim_daily_reward(user_id: int, guild_id: int) -> Optional[Dict[str, int]]:
    """Claim daily login reward"""
    async with db_pool.acquire() as conn:
        # Check last claim
        last_claim = await conn.fetchval('''
            SELECT last_daily_claim FROM users 
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)
        
        now = datetime.now()
        
        # Check if already claimed today
        if last_claim and last_claim.date() == now.date():
            return None
        
        # Check streak
        streak = await conn.fetchval('''
            SELECT current_streak FROM users 
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id) or 0
        
        # Calculate if streak continues (claimed yesterday)
        if last_claim and (now.date() - last_claim.date()).days == 1:
            streak += 1
        elif not last_claim or (now.date() - last_claim.date()).days > 1:
            streak = 1
        
        # Bonus for streaks
        sq_reward = 30 + (min(streak, 7) * 5)  # +5 SQ per day, max 7 days
        ticket_reward = 1 if streak % 3 == 0 else 0  # Ticket every 3 days
        
        # Update database
        await conn.execute('''
            UPDATE users 
            SET saint_quartz = saint_quartz + $1,
                summon_tickets = summon_tickets + $2,
                last_daily_claim = $3,
                current_streak = $4,
                longest_streak = GREATEST(longest_streak, $4)
            WHERE user_id = $5 AND guild_id = $6
        ''', sq_reward, ticket_reward, now, streak, user_id, guild_id)
        
        return {
            "sq": sq_reward,
            "tickets": ticket_reward,
            "streak": streak
        }

async def get_user_stats(user_id: int, guild_id: int) -> Optional[Dict]:
    """Get user statistics"""
    async with db_pool.acquire() as conn:
        return await conn.fetchrow('''
            SELECT * FROM users WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

# ============================================================================
# SERVANT/SUMMON FUNCTIONS
# ============================================================================

async def add_summon(user_id: int, guild_id: int, servant: dict, rank: str) -> int:
    """Add a summon for a user and return servant ID"""
    await get_or_create_guild(guild_id)
    
    # Calculate base stats based on rank
    rank_multipliers = {
        "EX": 2.0,
        "S": 1.6,
        "A": 1.3,
        "B": 1.0,
        "C": 0.7
    }
    multiplier = rank_multipliers.get(rank, 1.0)
    
    base_attack = int(100 * multiplier)
    base_defense = int(100 * multiplier)
    base_hp = int(1000 * multiplier)
    base_speed = int(50 * multiplier)
    
    async with db_pool.acquire() as conn:
        # Ensure user exists
        await conn.execute('''
            INSERT INTO users (user_id, guild_id, saint_quartz, summon_tickets) 
            VALUES ($1, $2, 0, 0) 
            ON CONFLICT (user_id, guild_id) DO NOTHING
        ''', user_id, guild_id)
        
        # Add summon and return ID
        servant_id = await conn.fetchval('''
            INSERT INTO summons (
                user_id, guild_id, servant_name, servant_class, servant_rank, 
                description, noble_phantasm, image_url,
                base_attack, base_defense, base_hp, base_speed
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
        ''', user_id, guild_id, servant['name'], servant['class'], rank, 
           servant['description'], servant['noble_phantasm'], servant.get('image_url'),
           base_attack, base_defense, base_hp, base_speed)
        
        # Increment total summons
        await conn.execute('''
            UPDATE users SET total_summons = total_summons + 1
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)
        
        return servant_id

async def get_user_summons(user_id: int, guild_id: int):
    """Get all summons for a user in a guild"""
    async with db_pool.acquire() as conn:
        return await conn.fetch('''
            SELECT * FROM summons 
            WHERE user_id = $1 AND guild_id = $2 
            ORDER BY is_favorite DESC, level DESC, summoned_at DESC
        ''', user_id, guild_id)

async def get_servant_by_id(servant_id: int):
    """Get servant by ID"""
    async with db_pool.acquire() as conn:
        return await conn.fetchrow('''
            SELECT * FROM summons WHERE id = $1
        ''', servant_id)

async def remove_summon(summon_id: int, guild_id: int) -> bool:
    """Remove a summon by ID"""
    async with db_pool.acquire() as conn:
        result = await conn.execute('''
            DELETE FROM summons WHERE id = $1 AND guild_id = $2
        ''', summon_id, guild_id)
        return result != "DELETE 0"

async def clear_user_summons(user_id: int, guild_id: int):
    """Clear all summons for a user"""
    async with db_pool.acquire() as conn:
        await conn.execute('''
            DELETE FROM summons WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

async def toggle_favorite_servant(servant_id: int) -> bool:
    """Toggle favorite status of a servant"""
    async with db_pool.acquire() as conn:
        new_status = await conn.fetchval('''
            UPDATE summons 
            SET is_favorite = NOT is_favorite
            WHERE id = $1
            RETURNING is_favorite
        ''', servant_id)
        return new_status

# ============================================================================
# LEVELING FUNCTIONS
# ============================================================================

async def add_experience(servant_id: int, exp: int) -> Dict:
    """Add experience to a servant and handle level ups"""
    async with db_pool.acquire() as conn:
        servant = await conn.fetchrow('SELECT * FROM summons WHERE id = $1', servant_id)
        
        if not servant:
            return None
        
        current_level = servant['level']
        current_exp = servant['experience']
        new_exp = current_exp + exp
        
        # Level up calculation (100 * level for next level)
        levels_gained = 0
        total_stats_gained = 0
        
        while new_exp >= (current_level * 100) and current_level < 100:
            new_exp -= (current_level * 100)
            current_level += 1
            levels_gained += 1
            # Each level gives +2 to all base stats
            total_stats_gained += 2
        
        if levels_gained > 0:
            await conn.execute('''
                UPDATE summons 
                SET level = $1, 
                    experience = $2,
                    base_attack = base_attack + $3,
                    base_defense = base_defense + $3,
                    base_hp = base_hp + ($3 * 10),
                    base_speed = base_speed + $3
                WHERE id = $4
            ''', current_level, new_exp, total_stats_gained, servant_id)
        else:
            await conn.execute('''
                UPDATE summons SET experience = $1 WHERE id = $2
            ''', new_exp, servant_id)
        
        return {
            "level": current_level,
            "exp": new_exp,
            "levels_gained": levels_gained,
            "exp_needed": current_level * 100
        }

async def get_servant_stats(servant_id: int) -> Dict:
    """Get total stats for a servant (base + bonuses + equipment)"""
    async with db_pool.acquire() as conn:
        servant = await conn.fetchrow('SELECT * FROM summons WHERE id = $1', servant_id)
        
        if not servant:
            return None
        
        # Get equipped items bonuses
        equipped_items = await conn.fetch('''
            SELECT i.stat_type, i.stat_value 
            FROM equipped_items ei
            JOIN items i ON ei.item_id = i.id
            WHERE ei.servant_id = $1 AND i.stat_type IS NOT NULL
        ''', servant_id)
        
        item_bonuses = {
            "attack": 0,
            "defense": 0,
            "hp": 0,
            "speed": 0
        }
        
        for item in equipped_items:
            if item['stat_type'] in item_bonuses:
                item_bonuses[item['stat_type']] += item['stat_value']
        
        return {
            "id": servant['id'],
            "name": servant['servant_name'],
            "class": servant['servant_class'],
            "rank": servant['servant_rank'],
            "level": servant['level'],
            "attack": servant['base_attack'] + servant['bonus_attack'] + item_bonuses['attack'],
            "defense": servant['base_defense'] + servant['bonus_defense'] + item_bonuses['defense'],
            "hp": servant['base_hp'] + servant['bonus_hp'] + item_bonuses['hp'],
            "speed": servant['base_speed'] + servant['bonus_speed'] + item_bonuses['speed'],
            "wins": servant['battles_won'],
            "total_battles": servant['total_battles']
        }

# ============================================================================
# ITEM & EQUIPMENT FUNCTIONS
# ============================================================================

async def get_item_by_name(item_name: str):
    """Get item by name"""
    async with db_pool.acquire() as conn:
        return await conn.fetchrow('''
            SELECT * FROM items WHERE name = $1
        ''', item_name)

async def get_all_items():
    """Get all available items"""
    async with db_pool.acquire() as conn:
        return await conn.fetch('SELECT * FROM items ORDER BY rarity DESC, price DESC')

async def get_user_inventory(user_id: int, guild_id: int):
    """Get user's inventory"""
    async with db_pool.acquire() as conn:
        return await conn.fetch('''
            SELECT i.*, inv.quantity, inv.acquired_at
            FROM inventory inv
            JOIN items i ON inv.item_id = i.id
            WHERE inv.user_id = $1 AND inv.guild_id = $2
            ORDER BY i.rarity DESC, i.price DESC
        ''', user_id, guild_id)

async def add_item_to_inventory(user_id: int, guild_id: int, item_id: int, quantity: int = 1):
    """Add item to user's inventory"""
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO inventory (user_id, guild_id, item_id, quantity)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, guild_id, item_id) 
            DO UPDATE SET quantity = inventory.quantity + $4
        ''', user_id, guild_id, item_id, quantity)

async def remove_item_from_inventory(user_id: int, guild_id: int, item_id: int, quantity: int = 1) -> bool:
    """Remove item from inventory"""
    async with db_pool.acquire() as conn:
        current_qty = await conn.fetchval('''
            SELECT quantity FROM inventory 
            WHERE user_id = $1 AND guild_id = $2 AND item_id = $3
        ''', user_id, guild_id, item_id)
        
        if not current_qty or current_qty < quantity:
            return False
        
        if current_qty == quantity:
            await conn.execute('''
                DELETE FROM inventory 
                WHERE user_id = $1 AND guild_id = $2 AND item_id = $3
            ''', user_id, guild_id, item_id)
        else:
            await conn.execute('''
                UPDATE inventory SET quantity = quantity - $4
                WHERE user_id = $1 AND guild_id = $2 AND item_id = $3
            ''', user_id, guild_id, item_id, quantity)
        
        return True

async def equip_item(servant_id: int, item_id: int, slot_type: str) -> bool:
    """Equip item to servant"""
    async with db_pool.acquire() as conn:
        # Check if slot is already occupied
        existing = await conn.fetchval('''
            SELECT id FROM equipped_items 
            WHERE servant_id = $1 AND slot_type = $2
        ''', servant_id, slot_type)
        
        if existing:
            # Unequip old item
            await conn.execute('''
                DELETE FROM equipped_items WHERE id = $1
            ''', existing)
        
        # Equip new item
        await conn.execute('''
            INSERT INTO equipped_items (servant_id, item_id, slot_type)
            VALUES ($1, $2, $3)
        ''', servant_id, item_id, slot_type)
        
        return True

async def unequip_item(servant_id: int, slot_type: str) -> bool:
    """Unequip item from servant"""
    async with db_pool.acquire() as conn:
        result = await conn.execute('''
            DELETE FROM equipped_items 
            WHERE servant_id = $1 AND slot_type = $2
        ''', servant_id, slot_type)
        return result != "DELETE 0"

async def get_equipped_items(servant_id: int):
    """Get all equipped items for a servant"""
    async with db_pool.acquire() as conn:
        return await conn.fetch('''
            SELECT ei.*, i.name, i.description, i.item_type, i.rarity, i.stat_type, i.stat_value
            FROM equipped_items ei
            JOIN items i ON ei.item_id = i.id
            WHERE ei.servant_id = $1
        ''', servant_id)

# ============================================================================
# BATTLE FUNCTIONS
# ============================================================================

async def create_battle(
    guild_id: int,
    challenger_id: int,
    opponent_id: int,
    challenger_servant_id: int,
    opponent_servant_id: int,
    forum_thread_id: Optional[int] = None,
    battle_type: str = "ranked"
) -> int:
    """Create a new battle"""
    async with db_pool.acquire() as conn:
        battle_id = await conn.fetchval('''
            INSERT INTO battles (
                guild_id, challenger_id, opponent_id,
                challenger_servant_id, opponent_servant_id,
                forum_thread_id, battle_type
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        ''', guild_id, challenger_id, opponent_id, 
           challenger_servant_id, opponent_servant_id,
           forum_thread_id, battle_type)
        
        return battle_id

async def complete_battle(
    battle_id: int,
    winner_id: int,
    battle_log: str,
    elo_change: int,
    exp_gained: int
):
    """Complete a battle and update stats"""
    async with db_pool.acquire() as conn:
        battle = await conn.fetchrow('SELECT * FROM battles WHERE id = $1', battle_id)
        
        if not battle:
            return
        
        loser_id = battle['opponent_id'] if winner_id == battle['challenger_id'] else battle['challenger_id']
        winner_servant_id = battle['challenger_servant_id'] if winner_id == battle['challenger_id'] else battle['opponent_servant_id']
        loser_servant_id = battle['opponent_servant_id'] if winner_id == battle['challenger_id'] else battle['challenger_servant_id']
        
        # Update battle record
        await conn.execute('''
            UPDATE battles 
            SET winner_id = $1, battle_log = $2, elo_change = $3, 
                experience_gained = $4, completed_at = $5
            WHERE id = $6
        ''', winner_id, battle_log, elo_change, exp_gained, datetime.now(), battle_id)
        
        # Update user stats
        await conn.execute('''
            UPDATE users 
            SET battle_wins = battle_wins + 1,
                elo_rating = elo_rating + $1
            WHERE user_id = $2 AND guild_id = $3
        ''', elo_change, winner_id, battle['guild_id'])
        
        await conn.execute('''
            UPDATE users 
            SET battle_losses = battle_losses + 1,
                elo_rating = GREATEST(elo_rating - $1, 0),
                current_streak = 0
            WHERE user_id = $2 AND guild_id = $3
        ''', elo_change, loser_id, battle['guild_id'])
        
        # Update servant stats
        await conn.execute('''
            UPDATE summons 
            SET battles_won = battles_won + 1,
                total_battles = total_battles + 1,
                last_battle = $1
            WHERE id = $2
        ''', datetime.now(), winner_servant_id)
        
        await conn.execute('''
            UPDATE summons 
            SET total_battles = total_battles + 1,
                last_battle = $1
            WHERE id = $2
        ''', datetime.now(), loser_servant_id)
        
        # Add experience to winner's servant
        await add_experience(winner_servant_id, exp_gained)

async def get_user_battle_history(user_id: int, guild_id: int, limit: int = 10):
    """Get user's recent battles"""
    async with db_pool.acquire() as conn:
        return await conn.fetch('''
            SELECT * FROM battles
            WHERE guild_id = $1 
            AND (challenger_id = $2 OR opponent_id = $2)
            AND completed_at IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT $3
        ''', guild_id, user_id, limit)

# ============================================================================
# COOLDOWN FUNCTIONS
# ============================================================================

async def check_cooldown(user_id: int, guild_id: int, action_type: str) -> Optional[datetime]:
    """Check if user has an active cooldown for an action"""
    async with db_pool.acquire() as conn:
        expires_at = await conn.fetchval('''
            SELECT expires_at FROM cooldowns
            WHERE user_id = $1 AND guild_id = $2 AND action_type = $3
            AND expires_at > $4
        ''', user_id, guild_id, action_type, datetime.now())
        
        return expires_at

async def set_cooldown(user_id: int, guild_id: int, action_type: str, duration_seconds: int):
    """Set a cooldown for a user action"""
    expires_at = datetime.now() + timedelta(seconds=duration_seconds)
    
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO cooldowns (user_id, guild_id, action_type, expires_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, guild_id, action_type)
            DO UPDATE SET expires_at = $4
        ''', user_id, guild_id, action_type, expires_at)

async def clear_expired_cooldowns():
    """Clear all expired cooldowns"""
    async with db_pool.acquire() as conn:
        await conn.execute('''
            DELETE FROM cooldowns WHERE expires_at <= $1
        ''', datetime.now())

# ============================================================================
# LEADERBOARD FUNCTIONS
# ============================================================================

async def get_elo_leaderboard(guild_id: int, limit: int = 10):
    """Get top players by ELO rating"""
    async with db_pool.acquire() as conn:
        return await conn.fetch('''
            SELECT user_id, elo_rating, battle_wins, battle_losses
            FROM users
            WHERE guild_id = $1 AND is_registered = TRUE
            ORDER BY elo_rating DESC
            LIMIT $2
        ''', guild_id, limit)

async def get_servant_leaderboard(guild_id: int, limit: int = 10):
    """Get top servants by level"""
    async with db_pool.acquire() as conn:
        return await conn.fetch('''
            SELECT s.*, u.user_id
            FROM summons s
            JOIN users u ON s.user_id = u.user_id AND s.guild_id = u.guild_id
            WHERE s.guild_id = $1
            ORDER BY s.level DESC, s.experience DESC
            LIMIT $2
        ''', guild_id, limit)

# ============================================================================
# ADMIN LOG FUNCTIONS
# ============================================================================

async def log_admin_action(
    guild_id: int,
    admin_id: int,
    action_type: str,
    target_user_id: Optional[int] = None,
    details: Optional[str] = None
):
    """Log an admin action"""
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO admin_logs (guild_id, admin_id, action_type, target_user_id, details)
            VALUES ($1, $2, $3, $4, $5)
        ''', guild_id, admin_id, action_type, target_user_id, details)

async def get_admin_logs(guild_id: int, limit: int = 50):
    """Get recent admin actions"""
    async with db_pool.acquire() as conn:
        return await conn.fetch('''
            SELECT * FROM admin_logs
            WHERE guild_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        ''', guild_id, limit)

# ============================================================================
# REGISTRATION FUNCTIONS
# ============================================================================

async def set_registration_config(guild_id: int, role_id: int, channel_id: int, message_id: int):
    """Set registration configuration"""
    await get_or_create_guild(guild_id)
    async with db_pool.acquire() as conn:
        await conn.execute('''
            UPDATE guilds 
            SET registration_role_id = $1, registration_channel_id = $2, registration_message_id = $3
            WHERE guild_id = $4
        ''', role_id, channel_id, message_id, guild_id)

async def get_registration_config(guild_id: int):
    """Get registration configuration"""
    async with db_pool.acquire() as conn:
        return await conn.fetchrow('''
            SELECT registration_role_id, registration_channel_id, registration_message_id
            FROM guilds WHERE guild_id = $1
        ''', guild_id)

# ============================================================================
# MISSION FUNCTIONS
# ============================================================================

async def get_daily_missions():
    """Get all daily missions"""
    async with db_pool.acquire() as conn:
        return await conn.fetch('SELECT * FROM daily_missions')

async def get_user_mission_progress(user_id: int, guild_id: int):
    """Get user's mission progress for today"""
    async with db_pool.acquire() as conn:
        return await conn.fetch('''
            SELECT ump.*, dm.description, dm.requirement, dm.sq_reward, dm.ticket_reward
            FROM user_mission_progress ump
            JOIN daily_missions dm ON ump.mission_id = dm.id
            WHERE ump.user_id = $1 AND ump.guild_id = $2 AND ump.reset_date = CURRENT_DATE
        ''', user_id, guild_id)

async def update_mission_progress(user_id: int, guild_id: int, mission_type: str, amount: int = 1):
    """Update progress for a mission type"""
    async with db_pool.acquire() as conn:
        # Get mission ID
        mission = await conn.fetchrow('''
            SELECT id, requirement FROM daily_missions WHERE mission_type = $1
        ''', mission_type)
        
        if not mission:
            return
        
        # Update or create progress
        await conn.execute('''
            INSERT INTO user_mission_progress (user_id, guild_id, mission_id, progress, reset_date)
            VALUES ($1, $2, $3, $4, CURRENT_DATE)
            ON CONFLICT (user_id, guild_id, mission_id, reset_date)
            DO UPDATE SET progress = user_mission_progress.progress + $4
        ''', user_id, guild_id, mission['id'], amount)
        
        # Check if completed
        current_progress = await conn.fetchval('''
            SELECT progress FROM user_mission_progress
            WHERE user_id = $1 AND guild_id = $2 AND mission_id = $3 AND reset_date = CURRENT_DATE
        ''', user_id, guild_id, mission['id'])
        
        if current_progress >= mission['requirement']:
            await conn.execute('''
                UPDATE user_mission_progress 
                SET completed = TRUE
                WHERE user_id = $1 AND guild_id = $2 AND mission_id = $3 AND reset_date = CURRENT_DATE
            ''', user_id, guild_id, mission['id'])

async def claim_mission_reward(user_id: int, guild_id: int, mission_id: int) -> Optional[Dict]:
    """Claim reward for a completed mission"""
    async with db_pool.acquire() as conn:
        # Check if mission is completed and not claimed
        progress = await conn.fetchrow('''
            SELECT * FROM user_mission_progress
            WHERE user_id = $1 AND guild_id = $2 AND mission_id = $3 
            AND reset_date = CURRENT_DATE AND completed = TRUE AND claimed = FALSE
        ''', user_id, guild_id, mission_id)
        
        if not progress:
            return None
        
        # Get reward amounts
        mission = await conn.fetchrow('''
            SELECT sq_reward, ticket_reward FROM daily_missions WHERE id = $1
        ''', mission_id)
        
        # Give rewards
        await update_user_currency(user_id, guild_id, mission['sq_reward'], mission['ticket_reward'])
        
        # Mark as claimed
        await conn.execute('''
            UPDATE user_mission_progress SET claimed = TRUE
            WHERE user_id = $1 AND guild_id = $2 AND mission_id = $3 AND reset_date = CURRENT_DATE
        ''', user_id, guild_id, mission_id)
        
        return {
            "sq": mission['sq_reward'],
            "tickets": mission['ticket_reward']
        }
