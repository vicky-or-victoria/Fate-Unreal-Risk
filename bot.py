import discord
from discord.ext import commands
from discord import app_commands
import asyncpg
import os
from typing import Optional, Literal
import asyncio
from datetime import datetime
from servants_data import SERVANTS, get_rank_color, get_rank_emoji, get_class_emoji

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Database connection pool
db_pool = None

# Database Functions
async def init_db():
    """Initialize database connection and create tables"""
    global db_pool
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    db_pool = await asyncpg.create_pool(database_url)
    
    async with db_pool.acquire() as conn:
        # Create guilds table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id BIGINT PRIMARY KEY,
                max_summons INTEGER DEFAULT 1,
                registration_role_id BIGINT,
                registration_channel_id BIGINT,
                registration_message_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create users table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT,
                guild_id BIGINT,
                is_registered BOOLEAN DEFAULT FALSE,
                registered_at TIMESTAMP,
                PRIMARY KEY (user_id, guild_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
            )
        ''')
        
        # Create summons table
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
                summoned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id, guild_id) REFERENCES users(user_id, guild_id) ON DELETE CASCADE
            )
        ''')
        
        # Create index for faster queries
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_summons_user_guild 
            ON summons(user_id, guild_id)
        ''')

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

async def get_user_summons(user_id: int, guild_id: int):
    """Get all summons for a user in a guild"""
    async with db_pool.acquire() as conn:
        return await conn.fetch('''
            SELECT * FROM summons 
            WHERE user_id = $1 AND guild_id = $2 
            ORDER BY summoned_at DESC
        ''', user_id, guild_id)

async def add_summon(user_id: int, guild_id: int, servant: dict, rank: str):
    """Add a summon for a user"""
    await get_or_create_guild(guild_id)
    async with db_pool.acquire() as conn:
        # Ensure user exists
        await conn.execute('''
            INSERT INTO users (user_id, guild_id) 
            VALUES ($1, $2) 
            ON CONFLICT (user_id, guild_id) DO NOTHING
        ''', user_id, guild_id)
        
        # Add summon
        await conn.execute('''
            INSERT INTO summons (user_id, guild_id, servant_name, servant_class, servant_rank, description, noble_phantasm, image_url)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ''', user_id, guild_id, servant['name'], servant['class'], rank, 
           servant['description'], servant['noble_phantasm'], servant.get('image_url'))

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

async def register_user(user_id: int, guild_id: int):
    """Register a user"""
    await get_or_create_guild(guild_id)
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO users (user_id, guild_id, is_registered, registered_at)
            VALUES ($1, $2, TRUE, $3)
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

# UI Components
class ServantSelectView(discord.ui.View):
    """View for selecting a servant from a dropdown"""
    def __init__(self, rank: str, user: discord.Member):
        super().__init__(timeout=180)
        self.rank = rank
        self.user = user
        self.add_item(ServantSelect(rank, user))

class ServantSelect(discord.ui.Select):
    """Dropdown for selecting a servant"""
    def __init__(self, rank: str, user: discord.Member):
        self.rank = rank
        self.user = user
        
        servants = SERVANTS[rank]
        options = [
            discord.SelectOption(
                label=servant["name"][:100],
                description=f"{servant['class']} • {servant['description'][:50]}...",
                emoji=get_rank_emoji(rank)
            )
            for servant in servants[:25]  # Discord limit
        ]
        
        super().__init__(
            placeholder=f"✨ Choose your {rank}-Rank Servant...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"servant_select_{rank}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "❌ This summoning circle isn't yours!", 
                ephemeral=True
            )
            return
        
        # Check if user is registered
        if not await is_user_registered(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "❌ You must register first before summoning a Servant!", 
                ephemeral=True
            )
            return
        
        # Check max summons
        current_summons = await get_user_summons(interaction.user.id, interaction.guild.id)
        max_summons = await get_max_summons(interaction.guild.id)
        
        if len(current_summons) >= max_summons:
            await interaction.response.send_message(
                f"❌ You have reached the maximum number of summons ({max_summons})!\n"
                f"Use `/dismiss` to remove a servant first.",
                ephemeral=True
            )
            return
        
        # Get selected servant
        selected_name = self.values[0]
        servant = next((s for s in SERVANTS[self.rank] if s["name"] == selected_name), None)
        
        if not servant:
            await interaction.response.send_message("❌ Servant not found!", ephemeral=True)
            return
        
        # Add summon to database
        await add_summon(interaction.user.id, interaction.guild.id, servant, self.rank)
        
        # Create success embed
        embed = discord.Embed(
            title="✨ SUMMONING SUCCESSFUL ✨",
            description=f"**{interaction.user.mention}** has summoned a legendary Heroic Spirit!",
            color=get_rank_color(self.rank),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name=f"{get_rank_emoji(self.rank)} Servant Name",
            value=f"**{servant['name']}**",
            inline=True
        )
        
        embed.add_field(
            name=f"{get_class_emoji(servant['class'])} Class",
            value=f"**{servant['class']}**",
            inline=True
        )
        
        embed.add_field(
            name="⭐ Rank",
            value=f"**{self.rank}**",
            inline=True
        )
        
        embed.add_field(
            name="📜 Description",
            value=servant['description'],
            inline=False
        )
        
        embed.add_field(
            name="⚔️ Noble Phantasm",
            value=f"*{servant['noble_phantasm']}*",
            inline=False
        )
        
        # Add image if available
        if servant.get('image_url'):
            embed.set_image(url=servant['image_url'])
        
        embed.set_footer(text=f"Master: {interaction.user.display_name}")
        
        await interaction.response.edit_message(embed=embed, view=None)

class RankSelectView(discord.ui.View):
    """View for selecting a rank"""
    def __init__(self, user: discord.Member):
        super().__init__(timeout=180)
        self.user = user
        self.add_item(RankSelect(user))

class RankSelect(discord.ui.Select):
    """Dropdown for selecting a rank"""
    def __init__(self, user: discord.Member):
        self.user = user
        
        options = [
            discord.SelectOption(
                label="EX Rank",
                description="The mightiest Heroic Spirits - Legendary beings",
                emoji="⭐"
            ),
            discord.SelectOption(
                label="S Rank",
                description="Exceptionally powerful heroes and demigods",
                emoji="💎"
            ),
            discord.SelectOption(
                label="A Rank",
                description="Elite warriors and legendary figures",
                emoji="🔷"
            ),
            discord.SelectOption(
                label="B Rank",
                description="Skilled heroes with notable achievements",
                emoji="🔹"
            ),
            discord.SelectOption(
                label="C Rank",
                description="Capable servants with unique abilities",
                emoji="⚪"
            ),
        ]
        
        super().__init__(
            placeholder="🎴 Select a Rank to view available Servants...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="rank_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "❌ This summoning circle isn't yours!", 
                ephemeral=True
            )
            return
        
        rank = self.values[0].split()[0]  # Get "EX", "S", "A", "B", or "C"
        
        # Show servant selection
        view = ServantSelectView(rank, self.user)
        
        embed = discord.Embed(
            title=f"{get_rank_emoji(rank)} {rank}-Rank Servants",
            description=f"Select a Servant from the {rank} rank to summon!",
            color=get_rank_color(rank)
        )
        
        servants_list = "\n".join([
            f"{get_class_emoji(s['class'])} **{s['name']}** - *{s['class']}*"
            for s in SERVANTS[rank][:10]
        ])
        
        embed.add_field(
            name="Available Servants",
            value=servants_list,
            inline=False
        )
        
        embed.set_footer(text=f"Summoning for {interaction.user.display_name}")
        
        await interaction.response.edit_message(embed=embed, view=view)

class RegistrationButton(discord.ui.Button):
    """Button for user registration"""
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="Register as Master",
            emoji="📝",
            custom_id="register_button"
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Check if already registered
        if await is_user_registered(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "✅ You are already registered as a Master!",
                ephemeral=True
            )
            return
        
        # Get registration role
        config = await get_registration_config(interaction.guild.id)
        if not config or not config['registration_role_id']:
            await interaction.response.send_message(
                "❌ Registration role not configured!",
                ephemeral=True
            )
            return
        
        role = interaction.guild.get_role(config['registration_role_id'])
        if not role:
            await interaction.response.send_message(
                "❌ Registration role not found!",
                ephemeral=True
            )
            return
        
        # Register user and add role
        await register_user(interaction.user.id, interaction.guild.id)
        await interaction.user.add_roles(role)
        
        # Send success message
        embed = discord.Embed(
            title="✨ Registration Successful!",
            description=f"Welcome, **{interaction.user.display_name}**!\n\nYou are now registered as a Master and can summon Servants!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📜 Role Granted",
            value=role.mention,
            inline=True
        )
        
        embed.add_field(
            name="🎴 Next Steps",
            value="Use `/summon` to summon your first Servant!",
            inline=False
        )
        
        embed.set_footer(text="Holy Grail War System")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class RegistrationView(discord.ui.View):
    """Persistent view for registration"""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RegistrationButton())

class RemoveServantSelect(discord.ui.Select):
    """Dropdown for selecting a servant to remove"""
    def __init__(self, summons, target_user: discord.Member):
        self.target_user = target_user
        self.summons = summons
        
        options = [
            discord.SelectOption(
                label=f"{s['servant_name'][:50]}",
                description=f"{s['servant_class']} - Rank {s['servant_rank']}",
                value=str(s['id']),
                emoji=get_rank_emoji(s['servant_rank'])
            )
            for s in summons[:25]
        ]
        
        super().__init__(
            placeholder="Select a servant to dismiss...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        summon_id = int(self.values[0])
        
        # Remove summon
        success = await remove_summon(summon_id, interaction.guild.id)
        
        if success:
            # Find the removed servant
            removed = next((s for s in self.summons if s['id'] == summon_id), None)
            
            embed = discord.Embed(
                title="⚔️ Servant Dismissed",
                description=f"**{removed['servant_name']}** has returned to the Throne of Heroes.",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Master",
                value=self.target_user.mention,
                inline=True
            )
            
            embed.add_field(
                name="Class",
                value=removed['servant_class'],
                inline=True
            )
            
            embed.add_field(
                name="Rank",
                value=removed['servant_rank'],
                inline=True
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.send_message(
                "❌ Failed to remove servant!",
                ephemeral=True
            )

# Bot Events
@bot.event
async def on_ready():
    """Bot ready event"""
    print(f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print(f'  Fate Summoning System Online')
    print(f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print(f'  Bot: {bot.user.name}')
    print(f'  ID: {bot.user.id}')
    print(f'  Servers: {len(bot.guilds)}')
    print(f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    
    # Add persistent view
    bot.add_view(RegistrationView())
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        print(f'  Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'  Error syncing commands: {e}')
    
    print(f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')

# Slash Commands
@bot.tree.command(name="summon", description="Summon a Heroic Spirit from the Throne of Heroes")
async def summon(interaction: discord.Interaction):
    """Summon command"""
    # Check if user is registered
    if not await is_user_registered(interaction.user.id, interaction.guild.id):
        embed = discord.Embed(
            title="❌ Not Registered",
            description="You must register as a Master before summoning Servants!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Check max summons
    current_summons = await get_user_summons(interaction.user.id, interaction.guild.id)
    max_summons = await get_max_summons(interaction.guild.id)
    
    if len(current_summons) >= max_summons:
        embed = discord.Embed(
            title="❌ Maximum Summons Reached",
            description=f"You have reached the maximum number of summons ({max_summons})!",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Current Servants",
            value=f"{len(current_summons)}/{max_summons}",
            inline=True
        )
        embed.add_field(
            name="Solution",
            value="Use `/dismiss` to remove a servant first.",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Show rank selection
    view = RankSelectView(interaction.user)
    
    embed = discord.Embed(
        title="✨ HOLY GRAIL SUMMONING SYSTEM ✨",
        description="Select a rank to view available Heroic Spirits for summoning!",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="⭐ EX Rank",
        value="The mightiest Heroic Spirits",
        inline=True
    )
    
    embed.add_field(
        name="💎 S Rank",
        value="Exceptionally powerful heroes",
        inline=True
    )
    
    embed.add_field(
        name="🔷 A Rank",
        value="Elite legendary warriors",
        inline=True
    )
    
    embed.add_field(
        name="🔹 B Rank",
        value="Skilled notable heroes",
        inline=True
    )
    
    embed.add_field(
        name="⚪ C Rank",
        value="Capable unique servants",
        inline=True
    )
    
    embed.add_field(
        name="\u200b",
        value="\u200b",
        inline=True
    )
    
    embed.add_field(
        name="📊 Your Summons",
        value=f"{len(current_summons)}/{max_summons} slots used",
        inline=False
    )
    
    embed.set_footer(text=f"Master: {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="servants", description="View your summoned Heroic Spirits")
async def servants(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    """View servants command"""
    target_user = user or interaction.user
    
    summons = await get_user_summons(target_user.id, interaction.guild.id)
    max_summons = await get_max_summons(interaction.guild.id)
    
    if not summons:
        embed = discord.Embed(
            title="📭 No Servants Summoned",
            description=f"**{target_user.display_name}** has not summoned any Servants yet!",
            color=discord.Color.greyple()
        )
        embed.add_field(
            name="Get Started",
            value="Use `/summon` to summon your first Servant!",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"⚔️ {target_user.display_name}'s Servants",
        description=f"Summoned Heroic Spirits ({len(summons)}/{max_summons})",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    for i, summon in enumerate(summons, 1):
        embed.add_field(
            name=f"{get_rank_emoji(summon['servant_rank'])} {summon['servant_name']}",
            value=f"{get_class_emoji(summon['servant_class'])} **Class:** {summon['servant_class']}\n"
                  f"⭐ **Rank:** {summon['servant_rank']}\n"
                  f"⚔️ **NP:** {summon['noble_phantasm']}\n"
                  f"📜 {summon['description'][:100]}...",
            inline=False
        )
    
    # Set image to first servant if available
    if summons and summons[0].get('image_url'):
        embed.set_thumbnail(url=summons[0]['image_url'])
    
    embed.set_footer(text=f"Master: {target_user.display_name}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="dismiss", description="Dismiss one of your summoned Servants")
async def dismiss(interaction: discord.Interaction):
    """Dismiss servant command"""
    summons = await get_user_summons(interaction.user.id, interaction.guild.id)
    
    if not summons:
        embed = discord.Embed(
            title="❌ No Servants",
            description="You don't have any summoned Servants to dismiss!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    view = discord.ui.View(timeout=180)
    view.add_item(RemoveServantSelect(summons, interaction.user))
    
    embed = discord.Embed(
        title="⚔️ Dismiss a Servant",
        description="Select a Servant to dismiss and return to the Throne of Heroes.",
        color=discord.Color.orange()
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Admin Commands
@bot.tree.command(name="setmaxsummons", description="[ADMIN] Set the maximum number of summons per user")
@app_commands.describe(max_summons="Maximum number of summons allowed per user")
@app_commands.checks.has_permissions(administrator=True)
async def setmaxsummons(interaction: discord.Interaction, max_summons: int):
    """Set max summons command"""
    if max_summons < 1:
        await interaction.response.send_message("❌ Max summons must be at least 1!", ephemeral=True)
        return
    
    if max_summons > 20:
        await interaction.response.send_message("❌ Max summons cannot exceed 20!", ephemeral=True)
        return
    
    await set_max_summons(interaction.guild.id, max_summons)
    
    embed = discord.Embed(
        title="✅ Max Summons Updated",
        description=f"Maximum summons per user has been set to **{max_summons}**",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="adminassign", description="[ADMIN] Assign a Servant to a user")
@app_commands.describe(
    user="The user to assign the servant to",
    rank="The rank of the servant",
    servant_name="The name of the servant to assign"
)
@app_commands.checks.has_permissions(administrator=True)
async def adminassign(
    interaction: discord.Interaction, 
    user: discord.Member, 
    rank: Literal["EX", "S", "A", "B", "C"],
    servant_name: str
):
    """Admin assign servant command"""
    # Check if user is registered
    if not await is_user_registered(user.id, interaction.guild.id):
        await interaction.response.send_message(
            f"❌ {user.mention} is not registered! They must register first.",
            ephemeral=True
        )
        return
    
    # Check max summons
    current_summons = await get_user_summons(user.id, interaction.guild.id)
    max_summons = await get_max_summons(interaction.guild.id)
    
    if len(current_summons) >= max_summons:
        await interaction.response.send_message(
            f"❌ {user.mention} has reached the maximum number of summons ({max_summons})!",
            ephemeral=True
        )
        return
    
    # Find servant
    servant = next((s for s in SERVANTS[rank] if s["name"].lower() == servant_name.lower()), None)
    
    if not servant:
        available = ", ".join([s["name"] for s in SERVANTS[rank]])
        await interaction.response.send_message(
            f"❌ Servant '{servant_name}' not found in {rank} rank!\n\n**Available {rank} servants:** {available}",
            ephemeral=True
        )
        return
    
    # Add summon
    await add_summon(user.id, interaction.guild.id, servant, rank)
    
    embed = discord.Embed(
        title="✨ ADMIN SUMMON SUCCESSFUL ✨",
        description=f"Administrator **{interaction.user.display_name}** has granted a Servant to **{user.display_name}**!",
        color=get_rank_color(rank),
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name=f"{get_rank_emoji(rank)} Servant Name",
        value=f"**{servant['name']}**",
        inline=True
    )
    
    embed.add_field(
        name=f"{get_class_emoji(servant['class'])} Class",
        value=f"**{servant['class']}**",
        inline=True
    )
    
    embed.add_field(
        name="⭐ Rank",
        value=f"**{rank}**",
        inline=True
    )
    
    embed.add_field(
        name="👤 Master",
        value=user.mention,
        inline=False
    )
    
    # Add image if available
    if servant.get('image_url'):
        embed.set_image(url=servant['image_url'])
    
    embed.set_footer(text=f"Granted by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="adminremove", description="[ADMIN] Remove a Servant from a user")
@app_commands.describe(user="The user to remove a servant from")
@app_commands.checks.has_permissions(administrator=True)
async def adminremove(interaction: discord.Interaction, user: discord.Member):
    """Admin remove servant command"""
    summons = await get_user_summons(user.id, interaction.guild.id)
    
    if not summons:
        await interaction.response.send_message(
            f"❌ {user.mention} doesn't have any summoned Servants!",
            ephemeral=True
        )
        return
    
    view = discord.ui.View(timeout=180)
    view.add_item(RemoveServantSelect(summons, user))
    
    embed = discord.Embed(
        title="⚔️ Admin Remove Servant",
        description=f"Select a Servant to remove from **{user.display_name}**",
        color=discord.Color.orange()
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="setupregistration", description="[ADMIN] Setup registration system")
@app_commands.describe(
    role="The role to give to registered users",
    channel="The channel to post the registration message in"
)
@app_commands.checks.has_permissions(administrator=True)
async def setupregistration(interaction: discord.Interaction, role: discord.Role, channel: discord.TextChannel):
    """Setup registration command"""
    # Create registration embed
    embed = discord.Embed(
        title="📜 MASTER REGISTRATION SYSTEM",
        description="Welcome to the Holy Grail War!\n\n"
                    "Register to become a Master and gain the ability to summon powerful Heroic Spirits from the Throne of Heroes.",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="✨ Benefits of Registration",
        value="• Summon legendary Servants\n"
              "• Access to all summoning commands\n"
              "• Participate in the Holy Grail War\n"
              "• Build your team of Heroic Spirits",
        inline=False
    )
    
    embed.add_field(
        name="📝 Role Granted",
        value=role.mention,
        inline=True
    )
    
    embed.add_field(
        name="🎴 How to Register",
        value="Click the button below to register!",
        inline=True
    )
    
    embed.set_footer(text="Holy Grail War Registration System")
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    
    # Send registration message
    view = RegistrationView()
    message = await channel.send(embed=embed, view=view)
    
    # Save configuration
    await set_registration_config(interaction.guild.id, role.id, channel.id, message.id)
    
    # Confirm to admin
    confirm_embed = discord.Embed(
        title="✅ Registration System Setup Complete",
        description=f"Registration message has been posted in {channel.mention}",
        color=discord.Color.green()
    )
    
    confirm_embed.add_field(
        name="Role",
        value=role.mention,
        inline=True
    )
    
    confirm_embed.add_field(
        name="Channel",
        value=channel.mention,
        inline=True
    )
    
    await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

@bot.tree.command(name="servantlist", description="View all available Servants by rank")
@app_commands.describe(rank="The rank to view servants from")
async def servantlist(interaction: discord.Interaction, rank: Literal["EX", "S", "A", "B", "C"]):
    """Servant list command"""
    servants = SERVANTS[rank]
    
    embed = discord.Embed(
        title=f"{get_rank_emoji(rank)} {rank}-Rank Servants",
        description=f"All available Servants in the {rank} rank",
        color=get_rank_color(rank),
        timestamp=datetime.now()
    )
    
    for servant in servants:
        embed.add_field(
            name=f"{get_class_emoji(servant['class'])} {servant['name']}",
            value=f"**Class:** {servant['class']}\n"
                  f"**NP:** {servant['noble_phantasm']}\n"
                  f"*{servant['description'][:80]}...*",
            inline=False
        )
    
    embed.set_footer(text=f"Total {rank}-Rank Servants: {len(servants)}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="View Holy Grail War statistics")
async def stats(interaction: discord.Interaction):
    """Stats command"""
    async with db_pool.acquire() as conn:
        total_summons = await conn.fetchval('''
            SELECT COUNT(*) FROM summons WHERE guild_id = $1
        ''', interaction.guild.id)
        
        total_registered = await conn.fetchval('''
            SELECT COUNT(*) FROM users WHERE guild_id = $1 AND is_registered = TRUE
        ''', interaction.guild.id)
        
        most_summoned = await conn.fetchrow('''
            SELECT servant_name, servant_class, COUNT(*) as count
            FROM summons WHERE guild_id = $1
            GROUP BY servant_name, servant_class
            ORDER BY count DESC
            LIMIT 1
        ''', interaction.guild.id)
    
    max_summons = await get_max_summons(interaction.guild.id)
    
    embed = discord.Embed(
        title="📊 Holy Grail War Statistics",
        description=f"Server: **{interaction.guild.name}**",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="👥 Registered Masters",
        value=f"**{total_registered}** users",
        inline=True
    )
    
    embed.add_field(
        name="⚔️ Total Summons",
        value=f"**{total_summons}** servants",
        inline=True
    )
    
    embed.add_field(
        name="📈 Max Summons",
        value=f"**{max_summons}** per user",
        inline=True
    )
    
    if most_summoned:
        embed.add_field(
            name="🌟 Most Summoned",
            value=f"**{most_summoned['servant_name']}** ({most_summoned['servant_class']})\n"
                  f"Summoned {most_summoned['count']} times",
            inline=False
        )
    
    embed.set_footer(text="Holy Grail War System")
    
    await interaction.response.send_message(embed=embed)

# Error Handlers
@setmaxsummons.error
@adminassign.error
@adminremove.error
@setupregistration.error
async def admin_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        embed = discord.Embed(
            title="❌ Missing Permissions",
            description="You need Administrator permissions to use this command!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Main
async def main():
    """Main function"""
    await init_db()
    
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        raise ValueError("DISCORD_TOKEN environment variable not set")
    
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
