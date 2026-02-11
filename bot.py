import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
from typing import Optional, Literal
import asyncio
import random
from datetime import datetime, timedelta
from servants_data import SERVANTS, get_rank_color, get_rank_emoji, get_class_emoji
import database as db

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_enhanced_embed_color(rank: str) -> discord.Color:
    """Get enhanced colors with gradients"""
    colors = {
        "EX": discord.Color.from_rgb(255, 215, 0),  # Bright Gold
        "S": discord.Color.from_rgb(230, 126, 255),  # Purple
        "A": discord.Color.from_rgb(64, 224, 208),  # Turquoise
        "B": discord.Color.from_rgb(30, 144, 255),  # Dodger Blue
        "C": discord.Color.from_rgb(169, 169, 169),  # Dark Gray
    }
    return colors.get(rank, discord.Color.blue())

def format_stat_bar(current: int, maximum: int, length: int = 10) -> str:
    """Create a progress bar for stats"""
    filled = int((current / maximum) * length)
    bar = "█" * filled + "░" * (length - filled)
    return f"{bar} {current}/{maximum}"

def get_rarity_emoji(rank: str) -> str:
    """Get rarity emojis with sparkles"""
    emojis = {
        "EX": "✨",
        "S": "💎",
        "A": "🔷",
        "B": "🔹",
        "C": "⚪"
    }
    return emojis.get(rank, "⭐")

def calculate_elo_change(winner_elo: int, loser_elo: int) -> int:
    """Calculate ELO rating change"""
    k_factor = 32
    expected_score = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    return max(int(k_factor * (1 - expected_score)), 5)

def get_level_emoji(level: int) -> str:
    """Get emoji based on level milestones"""
    if level >= 90:
        return "👑"
    elif level >= 70:
        return "💫"
    elif level >= 50:
        return "⭐"
    elif level >= 30:
        return "✨"
    elif level >= 10:
        return "🌟"
    else:
        return "💠"

# ============================================================================
# BATTLE SIMULATION
# ============================================================================

async def simulate_battle(servant1_stats: dict, servant2_stats: dict) -> tuple:
    """
    Simulate a battle between two servants
    Returns: (winner_stats, loser_stats, battle_log)
    """
    s1 = servant1_stats.copy()
    s2 = servant2_stats.copy()
    
    # Add current HP
    s1['current_hp'] = s1['hp']
    s2['current_hp'] = s2['hp']
    
    battle_log = []
    turn = 0
    max_turns = 30
    
    # Determine first attack based on speed
    if s1['speed'] >= s2['speed']:
        attacker, defender = s1, s2
    else:
        attacker, defender = s2, s1
    
    battle_log.append(f"⚔️ **BATTLE START!**")
    battle_log.append(f"🎯 **{s1['name']}** vs **{s2['name']}**\n")
    
    while s1['current_hp'] > 0 and s2['current_hp'] > 0 and turn < max_turns:
        turn += 1
        
        # Calculate damage with variance (±20%)
        base_damage = max(1, attacker['attack'] - (defender['defense'] // 2))
        variance = random.uniform(0.8, 1.2)
        damage = int(base_damage * variance)
        
        # Critical hit chance (10% + 1% per 10 levels)
        crit_chance = 0.1 + (attacker['level'] * 0.01)
        is_crit = random.random() < crit_chance
        
        if is_crit:
            damage = int(damage * 1.5)
            battle_log.append(f"💥 **CRITICAL HIT!**")
        
        defender['current_hp'] -= damage
        
        battle_log.append(
            f"Turn {turn}: **{attacker['name']}** attacks **{defender['name']}** "
            f"for **{damage}** damage! "
            f"(HP: {max(0, defender['current_hp'])}/{defender['hp']})"
        )
        
        # Noble Phantasm chance (15% when HP < 50%)
        if defender['current_hp'] < defender['hp'] * 0.5:
            if random.random() < 0.15:
                np_damage = attacker['attack']
                defender['current_hp'] -= np_damage
                battle_log.append(
                    f"🌟 **{attacker['name']}** unleashes their Noble Phantasm for "
                    f"**{np_damage}** damage!"
                )
        
        # Swap attacker and defender
        attacker, defender = defender, attacker
        
        # Prevent infinite battles
        if turn >= max_turns:
            battle_log.append("\n⏱️ **Battle timeout! Winner determined by remaining HP.**")
            break
    
    # Determine winner
    if s1['current_hp'] > s2['current_hp']:
        winner, loser = s1, s2
    else:
        winner, loser = s2, s1
    
    battle_log.append(f"\n🏆 **{winner['name']}** is victorious!")
    battle_log.append(f"Final HP: **{max(0, winner['current_hp'])}/{winner['hp']}**")
    
    return winner, loser, "\n".join(battle_log)

# ============================================================================
# UI COMPONENTS
# ============================================================================

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
            for servant in servants[:25]
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
        
        if not await db.is_user_registered(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "❌ You must register first!", 
                ephemeral=True
            )
            return
        
        servants = SERVANTS[self.rank]
        selected_servant = next(s for s in servants if s["name"] == self.values[0])
        
        # Add to database and get servant ID
        servant_id = await db.add_summon(
            interaction.user.id,
            interaction.guild.id,
            selected_servant,
            self.rank
        )
        
        # Update mission progress
        await db.update_mission_progress(interaction.user.id, interaction.guild.id, "summon", 1)
        
        # Create enhanced embed
        embed = discord.Embed(
            title=f"{get_rarity_emoji(self.rank)} Servant Summoned!",
            description=f"**{selected_servant['name']}** has answered your call!",
            color=get_enhanced_embed_color(self.rank),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name=f"{get_class_emoji(selected_servant['class'])} Class",
            value=f"**{selected_servant['class']}**",
            inline=True
        )
        
        embed.add_field(
            name=f"{get_rank_emoji(self.rank)} Rank",
            value=f"**{self.rank}**",
            inline=True
        )
        
        embed.add_field(
            name="🌟 Level",
            value="**1**",
            inline=True
        )
        
        # Get and display base stats
        stats = await db.get_servant_stats(servant_id)
        
        embed.add_field(
            name="⚔️ Attack",
            value=f"**{stats['attack']}**",
            inline=True
        )
        
        embed.add_field(
            name="🛡️ Defense",
            value=f"**{stats['defense']}**",
            inline=True
        )
        
        embed.add_field(
            name="💗 HP",
            value=f"**{stats['hp']}**",
            inline=True
        )
        
        embed.add_field(
            name="⚡ Speed",
            value=f"**{stats['speed']}**",
            inline=True
        )
        
        embed.add_field(
            name="👤 Master",
            value=interaction.user.mention,
            inline=True
        )
        
        embed.add_field(
            name="🎴 Noble Phantasm",
            value=f"*{selected_servant['noble_phantasm']}*",
            inline=False
        )
        
        embed.add_field(
            name="📖 Description",
            value=selected_servant['description'],
            inline=False
        )
        
        if selected_servant.get('image_url'):
            embed.set_image(url=selected_servant['image_url'])
        
        embed.set_footer(text=f"Servant ID: {servant_id} • {interaction.guild.name}")
        
        await interaction.response.send_message(embed=embed, view=None)

class RegistrationView(discord.ui.View):
    """View for registration button"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="Register as Master",
        style=discord.ButtonStyle.primary,
        emoji="📜",
        custom_id="register_button"
    )
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await db.is_user_registered(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message(
                "✅ You're already registered as a Master!",
                ephemeral=True
            )
            return
        
        config = await db.get_registration_config(interaction.guild.id)
        
        if config and config['registration_role_id']:
            role = interaction.guild.get_role(config['registration_role_id'])
            if role:
                await interaction.user.add_roles(role)
        
        await db.register_user(interaction.user.id, interaction.guild.id)
        
        embed = discord.Embed(
            title="✅ Registration Successful!",
            description=f"Welcome to the Holy Grail War, {interaction.user.mention}!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="🎁 Starting Rewards",
            value="• **100** Saint Quartz\n• **3** Summon Tickets\n• **1** Free Summon",
            inline=False
        )
        
        embed.add_field(
            name="📋 Next Steps",
            value="• Use `/summon` to get your first Servant\n"
                  "• Use `/daily` to claim daily rewards\n"
                  "• Use `/missions` to view available missions",
            inline=False
        )
        
        embed.set_footer(text="Good luck, Master!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class RemoveServantSelect(discord.ui.Select):
    """Dropdown for removing a servant"""
    def __init__(self, summons, user: discord.Member):
        self.target_user = user
        
        options = [
            discord.SelectOption(
                label=f"{s['servant_name']} (Lv.{s['level']})",
                description=f"{s['servant_class']} • {s['servant_rank']} Rank",
                value=str(s['id']),
                emoji=get_rank_emoji(s['servant_rank'])
            )
            for s in summons[:25]
        ]
        
        super().__init__(
            placeholder="Select a Servant to remove...",
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        servant_id = int(self.values[0])
        servant = await db.get_servant_by_id(servant_id)
        
        if await db.remove_summon(servant_id, interaction.guild.id):
            embed = discord.Embed(
                title="🗑️ Servant Removed",
                description=f"**{servant['servant_name']}** has been removed from {self.target_user.mention}'s roster.",
                color=discord.Color.orange()
            )
            
            await db.log_admin_action(
                interaction.guild.id,
                interaction.user.id,
                "remove_servant",
                self.target_user.id,
                f"Removed {servant['servant_name']}"
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Failed to remove servant!",
                ephemeral=True
            )

class ServantDetailView(discord.ui.View):
    """View for detailed servant information with buttons"""
    def __init__(self, servant_id: int, user_id: int):
        super().__init__(timeout=180)
        self.servant_id = servant_id
        self.user_id = user_id
    
    @discord.ui.button(label="⭐ Favorite", style=discord.ButtonStyle.primary)
    async def favorite_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ This isn't your servant!",
                ephemeral=True
            )
            return
        
        is_fav = await db.toggle_favorite_servant(self.servant_id)
        
        await interaction.response.send_message(
            f"{'⭐ Added to' if is_fav else '❌ Removed from'} favorites!",
            ephemeral=True
        )
    
    @discord.ui.button(label="🎒 Equipment", style=discord.ButtonStyle.secondary)
    async def equipment_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ This isn't your servant!",
                ephemeral=True
            )
            return
        
        equipped = await db.get_equipped_items(self.servant_id)
        
        embed = discord.Embed(
            title="🎒 Equipped Items",
            color=discord.Color.blue()
        )
        
        if equipped:
            for item in equipped:
                bonus = f"+{item['stat_value']} {item['stat_type'].title()}" if item['stat_value'] else "Special Effect"
                embed.add_field(
                    name=f"{get_rarity_emoji(item['rarity'])} {item['name']}",
                    value=f"*{item['description']}*\n**Bonus:** {bonus}",
                    inline=False
                )
        else:
            embed.description = "No items equipped."
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class BattleChallengeView(discord.ui.View):
    """View for accepting/declining battle challenges"""
    def __init__(self, challenger_id: int, opponent_id: int, challenger_servant_id: int):
        super().__init__(timeout=300)
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.challenger_servant_id = challenger_servant_id
    
    @discord.ui.button(label="⚔️ Accept Challenge", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message(
                "❌ This challenge isn't for you!",
                ephemeral=True
            )
            return
        
        # Show servant selection
        summons = await db.get_user_summons(self.opponent_id, interaction.guild.id)
        
        if not summons:
            await interaction.response.send_message(
                "❌ You don't have any servants to battle with!",
                ephemeral=True
            )
            return
        
        view = SelectServantForBattleView(
            summons,
            self.challenger_id,
            self.opponent_id,
            self.challenger_servant_id
        )
        
        await interaction.response.send_message(
            "⚔️ Select your champion for battle:",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message(
                "❌ This challenge isn't for you!",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            "⚔️ Challenge declined.",
            ephemeral=True
        )
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.message.edit(view=self)

class SelectServantForBattleView(discord.ui.View):
    """View for selecting which servant to use in battle"""
    def __init__(self, summons, challenger_id: int, opponent_id: int, challenger_servant_id: int):
        super().__init__(timeout=180)
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.challenger_servant_id = challenger_servant_id
        self.add_item(ServantBattleSelect(summons, challenger_id, opponent_id, challenger_servant_id))

class ServantBattleSelect(discord.ui.Select):
    """Dropdown for selecting servant for battle"""
    def __init__(self, summons, challenger_id: int, opponent_id: int, challenger_servant_id: int):
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.challenger_servant_id = challenger_servant_id
        
        options = [
            discord.SelectOption(
                label=f"{s['servant_name']} (Lv.{s['level']})",
                description=f"ATK: {s['base_attack']} | DEF: {s['base_defense']} | HP: {s['base_hp']}",
                value=str(s['id']),
                emoji=get_level_emoji(s['level'])
            )
            for s in summons[:25]
        ]
        
        super().__init__(
            placeholder="Choose your champion...",
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        opponent_servant_id = int(self.values[0])
        
        # Check cooldown
        cooldown = await db.check_cooldown(interaction.user.id, interaction.guild.id, "battle")
        if cooldown:
            remaining = (cooldown - datetime.now()).total_seconds()
            await interaction.response.send_message(
                f"⏱️ Battle cooldown active! Try again in {int(remaining)} seconds.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Get servant stats
        s1_stats = await db.get_servant_stats(self.challenger_servant_id)
        s2_stats = await db.get_servant_stats(opponent_servant_id)
        
        # Simulate battle
        winner, loser, battle_log = await simulate_battle(s1_stats, s2_stats)
        
        # Determine winner user ID
        winner_id = self.challenger_id if winner['id'] == self.challenger_servant_id else self.opponent_id
        
        # Calculate rewards
        challenger_user = await db.get_user_stats(self.challenger_id, interaction.guild.id)
        opponent_user = await db.get_user_stats(self.opponent_id, interaction.guild.id)
        
        elo_change = calculate_elo_change(
            challenger_user['elo_rating'] if winner_id == self.challenger_id else opponent_user['elo_rating'],
            opponent_user['elo_rating'] if winner_id == self.challenger_id else challenger_user['elo_rating']
        )
        
        exp_gained = 50 + (loser['level'] * 5)
        
        # Get battle forum
        forum_id = await db.get_battle_forum(interaction.guild.id)
        thread = None
        
        if forum_id:
            forum = interaction.guild.get_channel(forum_id)
            if forum and isinstance(forum, discord.ForumChannel):
                # Create battle thread
                challenger_user_obj = interaction.guild.get_member(self.challenger_id)
                opponent_user_obj = interaction.guild.get_member(self.opponent_id)
                
                thread = await forum.create_thread(
                    name=f"⚔️ {s1_stats['name']} vs {s2_stats['name']}",
                    content=f"**Battle between {challenger_user_obj.mention} and {opponent_user_obj.mention}**\n\n{battle_log}"
                )
        
        # Save battle to database
        battle_id = await db.create_battle(
            interaction.guild.id,
            self.challenger_id,
            self.opponent_id,
            self.challenger_servant_id,
            opponent_servant_id,
            thread.thread.id if thread else None,
            "ranked"
        )
        
        await db.complete_battle(battle_id, winner_id, battle_log, elo_change, exp_gained)
        
        # Set cooldown (5 minutes)
        await db.set_cooldown(self.challenger_id, interaction.guild.id, "battle", 300)
        await db.set_cooldown(self.opponent_id, interaction.guild.id, "battle", 300)
        
        # Update mission progress
        await db.update_mission_progress(winner_id, interaction.guild.id, "battle", 1)
        
        # Create result embed
        embed = discord.Embed(
            title="⚔️ Battle Complete!",
            description=f"🏆 **{winner['name']}** is victorious!",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        winner_user = interaction.guild.get_member(winner_id)
        embed.add_field(
            name="👑 Victor",
            value=f"{winner_user.mention}'s **{winner['name']}**",
            inline=False
        )
        
        embed.add_field(
            name="📊 Rewards",
            value=f"• **+{elo_change}** ELO\n• **+{exp_gained}** EXP",
            inline=True
        )
        
        if thread:
            embed.add_field(
                name="📜 Battle Log",
                value=f"View full battle in {thread.thread.mention}",
                inline=True
            )
        
        embed.set_footer(text=f"Battle ID: {battle_id}")
        
        await interaction.followup.send(embed=embed)

# ============================================================================
# BOT EVENTS
# ============================================================================

@bot.event
async def on_ready():
    """Bot startup event"""
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    
    await db.init_db()
    print('Database initialized')
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
    
    # Start background tasks
    cleanup_cooldowns.start()
    print('Background tasks started')
    
    # Set bot presence
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the Holy Grail War"
        )
    )
    
    print('Bot is ready!')

@tasks.loop(minutes=5)
async def cleanup_cooldowns():
    """Clean up expired cooldowns every 5 minutes"""
    await db.clear_expired_cooldowns()

# ============================================================================
# SUMMON COMMANDS
# ============================================================================

@bot.tree.command(name="summon", description="Summon a random Servant")
async def summon(interaction: discord.Interaction):
    """Random summon command"""
    if not await db.is_user_registered(interaction.user.id, interaction.guild.id):
        await interaction.response.send_message(
            "❌ You must register first! Ask an admin to set up registration.",
            ephemeral=True
        )
        return
    
    # Check servant limit
    max_summons = await db.get_max_summons(interaction.guild.id)
    current_summons = await db.get_user_summons(interaction.user.id, interaction.guild.id)
    
    if len(current_summons) >= max_summons:
        await interaction.response.send_message(
            f"❌ You've reached the maximum of {max_summons} Servants!",
            ephemeral=True
        )
        return
    
    # Check currency
    currency = await db.get_user_currency(interaction.user.id, interaction.guild.id)
    
    # Cost: 1 ticket or 30 SQ
    if currency['tickets'] > 0:
        await db.update_user_currency(interaction.user.id, interaction.guild.id, 0, -1)
        cost_msg = "1 Summon Ticket"
    elif currency['sq'] >= 30:
        await db.update_user_currency(interaction.user.id, interaction.guild.id, -30, 0)
        cost_msg = "30 Saint Quartz"
    else:
        await interaction.response.send_message(
            "❌ Insufficient currency! You need 1 Summon Ticket or 30 Saint Quartz.\n"
            f"**Current:** {currency['sq']} SQ, {currency['tickets']} Tickets\n"
            "💡 Use `/daily` to get more!",
            ephemeral=True
        )
        return
    
    # Gacha rates: EX: 1%, S: 5%, A: 15%, B: 30%, C: 49%
    roll = random.random() * 100
    
    if roll < 1:
        rank = "EX"
    elif roll < 6:
        rank = "S"
    elif roll < 21:
        rank = "A"
    elif roll < 51:
        rank = "B"
    else:
        rank = "C"
    
    # Show servant selection
    view = ServantSelectView(rank, interaction.user)
    
    embed = discord.Embed(
        title=f"{get_rarity_emoji(rank)} Summoning Circle",
        description=f"A {rank}-Rank Servant responds to your call!\n*Used: {cost_msg}*",
        color=get_enhanced_embed_color(rank),
        timestamp=datetime.now()
    )
    
    embed.set_footer(text="Choose your Servant from the dropdown below")
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="myservants", description="View your summoned Servants")
async def myservants(interaction: discord.Interaction):
    """View servants command"""
    summons = await db.get_user_summons(interaction.user.id, interaction.guild.id)
    
    if not summons:
        await interaction.response.send_message(
            "❌ You haven't summoned any Servants yet!\nUse `/summon` to get started!",
            ephemeral=True
        )
        return
    
    max_summons = await db.get_max_summons(interaction.guild.id)
    
    embed = discord.Embed(
        title=f"📜 {interaction.user.display_name}'s Servants",
        description=f"**{len(summons)}/{max_summons}** Servants",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    for s in summons[:10]:  # Show max 10
        stats = await db.get_servant_stats(s['id'])
        
        fav_mark = "⭐ " if s['is_favorite'] else ""
        level_emoji = get_level_emoji(s['level'])
        
        value = (
            f"{level_emoji} **Level {s['level']}** | {get_rank_emoji(s['servant_rank'])} {s['servant_rank']}-Rank\n"
            f"⚔️ ATK: {stats['attack']} | 🛡️ DEF: {stats['defense']} | "
            f"💗 HP: {stats['hp']} | ⚡ SPD: {stats['speed']}\n"
            f"🏆 Wins: {s['battles_won']}/{s['total_battles']}"
        )
        
        embed.add_field(
            name=f"{fav_mark}{get_class_emoji(s['servant_class'])} {s['servant_name']}",
            value=value,
            inline=False
        )
    
    if len(summons) > 10:
        embed.set_footer(text=f"Showing 10 of {len(summons)} servants")
    
    await interaction.response.send_message(embed=embed)

# Continue in next part...

# ============================================================================
# ECONOMY & DAILY COMMANDS
# ============================================================================

@bot.tree.command(name="daily", description="Claim your daily login rewards")
async def daily(interaction: discord.Interaction):
    """Daily reward command"""
    if not await db.is_user_registered(interaction.user.id, interaction.guild.id):
        await interaction.response.send_message(
            "❌ You must register first!",
            ephemeral=True
        )
        return
    
    reward = await db.claim_daily_reward(interaction.user.id, interaction.guild.id)
    
    if not reward:
        await interaction.response.send_message(
            "⏱️ You've already claimed your daily reward today!\nCome back tomorrow!",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="🎁 Daily Login Reward",
        description="You've claimed your daily rewards!",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="💎 Saint Quartz",
        value=f"+**{reward['sq']}** SQ",
        inline=True
    )
    
    if reward['tickets'] > 0:
        embed.add_field(
            name="🎫 Summon Tickets",
            value=f"+**{reward['tickets']}** Tickets",
            inline=True
        )
    
    embed.add_field(
        name="🔥 Login Streak",
        value=f"**{reward['streak']}** days",
        inline=True
    )
    
    if reward['streak'] >= 7:
        embed.add_field(
            name="🏆 Streak Bonus",
            value="Maximum daily bonus reached!",
            inline=False
        )
    
    embed.set_footer(text="Come back tomorrow for more rewards!")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="balance", description="Check your Saint Quartz and tickets")
async def balance(interaction: discord.Interaction):
    """Balance command"""
    if not await db.is_user_registered(interaction.user.id, interaction.guild.id):
        await interaction.response.send_message(
            "❌ You must register first!",
            ephemeral=True
        )
        return
    
    currency = await db.get_user_currency(interaction.user.id, interaction.guild.id)
    stats = await db.get_user_stats(interaction.user.id, interaction.guild.id)
    
    embed = discord.Embed(
        title=f"💰 {interaction.user.display_name}'s Balance",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="💎 Saint Quartz",
        value=f"**{currency['sq']}** SQ",
        inline=True
    )
    
    embed.add_field(
        name="🎫 Summon Tickets",
        value=f"**{currency['tickets']}** Tickets",
        inline=True
    )
    
    embed.add_field(
        name="📊 Battle Stats",
        value=f"**{stats['battle_wins']}W** / **{stats['battle_losses']}L**",
        inline=True
    )
    
    embed.add_field(
        name="🏆 ELO Rating",
        value=f"**{stats['elo_rating']}**",
        inline=True
    )
    
    embed.add_field(
        name="🌟 Total Summons",
        value=f"**{stats['total_summons']}**",
        inline=True
    )
    
    embed.add_field(
        name="🔥 Current Streak",
        value=f"**{stats['current_streak']}** days",
        inline=True
    )
    
    embed.set_footer(text="Use /daily to claim rewards!")
    
    await interaction.response.send_message(embed=embed)

# ============================================================================
# SHOP & INVENTORY COMMANDS
# ============================================================================

@bot.tree.command(name="shop", description="Browse the item shop")
async def shop(interaction: discord.Interaction):
    """Shop command"""
    if not await db.is_user_registered(interaction.user.id, interaction.guild.id):
        await interaction.response.send_message(
            "❌ You must register first!",
            ephemeral=True
        )
        return
    
    items = await db.get_all_items()
    currency = await db.get_user_currency(interaction.user.id, interaction.guild.id)
    
    embed = discord.Embed(
        title="🏪 Item Shop",
        description=f"Your balance: **{currency['sq']}** SQ",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    # Group items by type
    item_types = {}
    for item in items:
        item_type = item['item_type']
        if item_type not in item_types:
            item_types[item_type] = []
        item_types[item_type].append(item)
    
    for item_type, type_items in list(item_types.items())[:5]:  # Show 5 types max
        items_text = []
        for item in type_items[:3]:  # Show 3 items per type
            bonus = f"+{item['stat_value']} {item['stat_type'].title()}" if item['stat_value'] else "Special"
            items_text.append(
                f"{get_rarity_emoji(item['rarity'])} **{item['name']}** - {item['price']} SQ\n"
                f"*{bonus}*"
            )
        
        embed.add_field(
            name=f"📦 {item_type.title().replace('_', ' ')}",
            value="\n".join(items_text),
            inline=False
        )
    
    embed.set_footer(text="Use /buy <item_name> to purchase")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buy", description="Buy an item from the shop")
@app_commands.describe(item_name="Name of the item to buy")
async def buy(interaction: discord.Interaction, item_name: str):
    """Buy item command"""
    if not await db.is_user_registered(interaction.user.id, interaction.guild.id):
        await interaction.response.send_message(
            "❌ You must register first!",
            ephemeral=True
        )
        return
    
    item = await db.get_item_by_name(item_name)
    
    if not item:
        await interaction.response.send_message(
            f"❌ Item '{item_name}' not found!",
            ephemeral=True
        )
        return
    
    currency = await db.get_user_currency(interaction.user.id, interaction.guild.id)
    
    if currency['sq'] < item['price']:
        await interaction.response.send_message(
            f"❌ Insufficient Saint Quartz!\n"
            f"**Required:** {item['price']} SQ\n"
            f"**You have:** {currency['sq']} SQ",
            ephemeral=True
        )
        return
    
    # Purchase item
    await db.update_user_currency(interaction.user.id, interaction.guild.id, -item['price'], 0)
    await db.add_item_to_inventory(interaction.user.id, interaction.guild.id, item['id'], 1)
    
    embed = discord.Embed(
        title="✅ Purchase Successful!",
        description=f"You bought **{item['name']}**!",
        color=discord.Color.green()
    )
    
    bonus = f"+{item['stat_value']} {item['stat_type'].title()}" if item['stat_value'] else "Special Effect"
    
    embed.add_field(
        name=f"{get_rarity_emoji(item['rarity'])} {item['name']}",
        value=f"*{item['description']}*\n**Bonus:** {bonus}",
        inline=False
    )
    
    embed.add_field(
        name="💰 Cost",
        value=f"{item['price']} SQ",
        inline=True
    )
    
    embed.add_field(
        name="💎 Remaining Balance",
        value=f"{currency['sq'] - item['price']} SQ",
        inline=True
    )
    
    embed.set_footer(text="Use /inventory to view your items")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="inventory", description="View your inventory")
async def inventory(interaction: discord.Interaction):
    """Inventory command"""
    if not await db.is_user_registered(interaction.user.id, interaction.guild.id):
        await interaction.response.send_message(
            "❌ You must register first!",
            ephemeral=True
        )
        return
    
    items = await db.get_user_inventory(interaction.user.id, interaction.guild.id)
    
    if not items:
        await interaction.response.send_message(
            "🎒 Your inventory is empty!\nUse `/shop` to buy items.",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title=f"🎒 {interaction.user.display_name}'s Inventory",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    for item in items[:15]:  # Show max 15 items
        bonus = f"+{item['stat_value']} {item['stat_type'].title()}" if item['stat_value'] else "Special"
        
        embed.add_field(
            name=f"{get_rarity_emoji(item['rarity'])} {item['name']} x{item['quantity']}",
            value=f"*{item['description']}*\n**Bonus:** {bonus}",
            inline=False
        )
    
    if len(items) > 15:
        embed.set_footer(text=f"Showing 15 of {len(items)} items")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="equip", description="Equip an item to a servant")
@app_commands.describe(
    servant_id="ID of the servant",
    item_name="Name of the item to equip"
)
async def equip(interaction: discord.Interaction, servant_id: int, item_name: str):
    """Equip item command"""
    if not await db.is_user_registered(interaction.user.id, interaction.guild.id):
        await interaction.response.send_message(
            "❌ You must register first!",
            ephemeral=True
        )
        return
    
    # Verify servant ownership
    servant = await db.get_servant_by_id(servant_id)
    
    if not servant or servant['user_id'] != interaction.user.id:
        await interaction.response.send_message(
            "❌ You don't own this servant!",
            ephemeral=True
        )
        return
    
    # Get item
    item = await db.get_item_by_name(item_name)
    
    if not item:
        await interaction.response.send_message(
            f"❌ Item '{item_name}' not found!",
            ephemeral=True
        )
        return
    
    # Check if user owns the item
    inventory_items = await db.get_user_inventory(interaction.user.id, interaction.guild.id)
    has_item = any(i['id'] == item['id'] for i in inventory_items)
    
    if not has_item:
        await interaction.response.send_message(
            "❌ You don't own this item!",
            ephemeral=True
        )
        return
    
    # Equip item
    slot_type = item['item_type']
    await db.equip_item(servant_id, item['id'], slot_type)
    
    # Update mission progress
    await db.update_mission_progress(interaction.user.id, interaction.guild.id, "use_item", 1)
    
    embed = discord.Embed(
        title="✅ Item Equipped!",
        description=f"**{item['name']}** equipped to **{servant['servant_name']}**!",
        color=discord.Color.green()
    )
    
    # Show new stats
    stats = await db.get_servant_stats(servant_id)
    
    embed.add_field(
        name="📊 Updated Stats",
        value=f"⚔️ ATK: {stats['attack']} | 🛡️ DEF: {stats['defense']}\n"
              f"💗 HP: {stats['hp']} | ⚡ SPD: {stats['speed']}",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

# ============================================================================
# BATTLE COMMANDS
# ============================================================================

@bot.tree.command(name="battle", description="Challenge another Master to battle")
@app_commands.describe(
    opponent="The Master to challenge",
    servant_id="Your servant's ID for battle"
)
async def battle(interaction: discord.Interaction, opponent: discord.Member, servant_id: int):
    """Battle command"""
    if not await db.is_user_registered(interaction.user.id, interaction.guild.id):
        await interaction.response.send_message(
            "❌ You must register first!",
            ephemeral=True
        )
        return
    
    if not await db.is_user_registered(opponent.id, interaction.guild.id):
        await interaction.response.send_message(
            "❌ Your opponent must be registered!",
            ephemeral=True
        )
        return
    
    if opponent.id == interaction.user.id:
        await interaction.response.send_message(
            "❌ You can't battle yourself!",
            ephemeral=True
        )
        return
    
    # Check cooldown
    cooldown = await db.check_cooldown(interaction.user.id, interaction.guild.id, "battle")
    if cooldown:
        remaining = int((cooldown - datetime.now()).total_seconds())
        await interaction.response.send_message(
            f"⏱️ Battle cooldown active! Try again in {remaining} seconds.",
            ephemeral=True
        )
        return
    
    # Verify servant ownership
    servant = await db.get_servant_by_id(servant_id)
    
    if not servant or servant['user_id'] != interaction.user.id:
        await interaction.response.send_message(
            "❌ You don't own this servant!",
            ephemeral=True
        )
        return
    
    # Create challenge embed
    embed = discord.Embed(
        title="⚔️ Battle Challenge!",
        description=f"{interaction.user.mention} challenges {opponent.mention} to battle!",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    
    stats = await db.get_servant_stats(servant_id)
    
    embed.add_field(
        name=f"{get_class_emoji(servant['servant_class'])} Challenger's Servant",
        value=f"**{servant['servant_name']}** (Lv.{servant['level']})\n"
              f"⚔️ {stats['attack']} | 🛡️ {stats['defense']} | "
              f"💗 {stats['hp']} | ⚡ {stats['speed']}",
        inline=False
    )
    
    embed.set_footer(text="Opponent: Select your servant to accept!")
    
    view = BattleChallengeView(interaction.user.id, opponent.id, servant_id)
    
    await interaction.response.send_message(content=opponent.mention, embed=embed, view=view)

# ============================================================================
# MISSION COMMANDS
# ============================================================================

@bot.tree.command(name="missions", description="View your daily missions")
async def missions(interaction: discord.Interaction):
    """Missions command"""
    if not await db.is_user_registered(interaction.user.id, interaction.guild.id):
        await interaction.response.send_message(
            "❌ You must register first!",
            ephemeral=True
        )
        return
    
    all_missions = await db.get_daily_missions()
    user_progress = await db.get_user_mission_progress(interaction.user.id, interaction.guild.id)
    
    # Create progress map
    progress_map = {p['mission_id']: p for p in user_progress}
    
    embed = discord.Embed(
        title="📋 Daily Missions",
        description="Complete missions to earn rewards!",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    for mission in all_missions:
        progress = progress_map.get(mission['id'])
        
        if progress:
            current = progress['progress']
            completed = progress['completed']
            claimed = progress['claimed']
        else:
            current = 0
            completed = False
            claimed = False
        
        # Status emoji
        if claimed:
            status = "✅ Claimed"
        elif completed:
            status = "🎁 Ready to claim!"
        else:
            status = f"📊 {current}/{mission['requirement']}"
        
        # Progress bar
        progress_bar = format_stat_bar(current, mission['requirement'], 8)
        
        rewards = f"💎 {mission['sq_reward']} SQ"
        if mission['ticket_reward'] > 0:
            rewards += f" + 🎫 {mission['ticket_reward']} Tickets"
        
        embed.add_field(
            name=f"{status} - {mission['description']}",
            value=f"{progress_bar}\n**Rewards:** {rewards}",
            inline=False
        )
    
    embed.set_footer(text="Use /claimmission <mission_type> to claim rewards")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="claimmission", description="Claim rewards for a completed mission")
@app_commands.describe(mission_type="Type of mission to claim")
async def claimmission(interaction: discord.Interaction, mission_type: str):
    """Claim mission command"""
    if not await db.is_user_registered(interaction.user.id, interaction.guild.id):
        await interaction.response.send_message(
            "❌ You must register first!",
            ephemeral=True
        )
        return
    
    # Get mission by type
    missions = await db.get_daily_missions()
    mission = next((m for m in missions if m['mission_type'] == mission_type), None)
    
    if not mission:
        await interaction.response.send_message(
            f"❌ Mission type '{mission_type}' not found!",
            ephemeral=True
        )
        return
    
    reward = await db.claim_mission_reward(interaction.user.id, interaction.guild.id, mission['id'])
    
    if not reward:
        await interaction.response.send_message(
            "❌ Mission not completed or already claimed!",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="🎁 Mission Reward Claimed!",
        description=f"You completed: **{mission['description']}**",
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="💎 Saint Quartz",
        value=f"+**{reward['sq']}** SQ",
        inline=True
    )
    
    if reward['tickets'] > 0:
        embed.add_field(
            name="🎫 Summon Tickets",
            value=f"+**{reward['tickets']}** Tickets",
            inline=True
        )
    
    await interaction.response.send_message(embed=embed)

# ============================================================================
# LEADERBOARD COMMANDS
# ============================================================================

@bot.tree.command(name="leaderboard", description="View server rankings")
@app_commands.describe(board_type="Type of leaderboard to view")
async def leaderboard(
    interaction: discord.Interaction,
    board_type: Literal["elo", "servants"] = "elo"
):
    """Leaderboard command"""
    if board_type == "elo":
        leaders = await db.get_elo_leaderboard(interaction.guild.id, 10)
        
        embed = discord.Embed(
            title="🏆 ELO Leaderboard",
            description="Top Masters by ELO Rating",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        
        for idx, leader in enumerate(leaders):
            user = interaction.guild.get_member(leader['user_id'])
            if user:
                winrate = (leader['battle_wins'] / (leader['battle_wins'] + leader['battle_losses']) * 100) if (leader['battle_wins'] + leader['battle_losses']) > 0 else 0
                
                embed.add_field(
                    name=f"{medals[idx]} {user.display_name}",
                    value=f"**ELO:** {leader['elo_rating']} | **W/L:** {leader['battle_wins']}/{leader['battle_losses']} ({winrate:.1f}%)",
                    inline=False
                )
    
    else:  # servants
        leaders = await db.get_servant_leaderboard(interaction.guild.id, 10)
        
        embed = discord.Embed(
            title="⭐ Servant Leaderboard",
            description="Top Servants by Level",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        
        for idx, servant in enumerate(leaders):
            user = interaction.guild.get_member(servant['user_id'])
            if user:
                level_emoji = get_level_emoji(servant['level'])
                
                embed.add_field(
                    name=f"{medals[idx]} {servant['servant_name']}",
                    value=f"{level_emoji} **Lv.{servant['level']}** | {get_rank_emoji(servant['servant_rank'])} {servant['servant_rank']}-Rank | Owner: {user.mention}",
                    inline=False
                )
    
    await interaction.response.send_message(embed=embed)

# ============================================================================
# ADMIN COMMANDS
# ============================================================================

@bot.tree.command(name="setmaxsummons", description="[ADMIN] Set maximum Servants per user")
@app_commands.describe(max_summons="Maximum number of Servants")
@app_commands.checks.has_permissions(administrator=True)
async def setmaxsummons(interaction: discord.Interaction, max_summons: int):
    """Set max summons command"""
    if max_summons < 1:
        await interaction.response.send_message(
            "❌ Maximum summons must be at least 1!",
            ephemeral=True
        )
        return
    
    await db.set_max_summons(interaction.guild.id, max_summons)
    
    await db.log_admin_action(
        interaction.guild.id,
        interaction.user.id,
        "set_max_summons",
        None,
        f"Set max summons to {max_summons}"
    )
    
    embed = discord.Embed(
        title="✅ Max Summons Updated",
        description=f"Maximum Servants per user set to **{max_summons}**",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setbattleforum", description="[ADMIN] Set the forum channel for battles")
@app_commands.describe(forum="The forum channel for battle threads")
@app_commands.checks.has_permissions(administrator=True)
async def setbattleforum(interaction: discord.Interaction, forum: discord.ForumChannel):
    """Set battle forum command"""
    await db.set_battle_forum(interaction.guild.id, forum.id)
    
    await db.log_admin_action(
        interaction.guild.id,
        interaction.user.id,
        "set_battle_forum",
        None,
        f"Set battle forum to {forum.name}"
    )
    
    embed = discord.Embed(
        title="✅ Battle Forum Set",
        description=f"Battle threads will be created in {forum.mention}",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="givecurrency", description="[ADMIN] Give currency to a user")
@app_commands.describe(
    user="User to give currency to",
    saint_quartz="Amount of Saint Quartz",
    tickets="Amount of summon tickets"
)
@app_commands.checks.has_permissions(administrator=True)
async def givecurrency(
    interaction: discord.Interaction,
    user: discord.Member,
    saint_quartz: int = 0,
    tickets: int = 0
):
    """Give currency command"""
    if saint_quartz == 0 and tickets == 0:
        await interaction.response.send_message(
            "❌ You must give at least some currency!",
            ephemeral=True
        )
        return
    
    await db.update_user_currency(user.id, interaction.guild.id, saint_quartz, tickets)
    
    await db.log_admin_action(
        interaction.guild.id,
        interaction.user.id,
        "give_currency",
        user.id,
        f"Gave {saint_quartz} SQ and {tickets} tickets"
    )
    
    embed = discord.Embed(
        title="💰 Currency Given",
        description=f"Gave currency to {user.mention}",
        color=discord.Color.green()
    )
    
    if saint_quartz > 0:
        embed.add_field(name="💎 Saint Quartz", value=f"+{saint_quartz}", inline=True)
    
    if tickets > 0:
        embed.add_field(name="🎫 Tickets", value=f"+{tickets}", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="adminassign", description="[ADMIN] Assign a specific Servant to a user")
@app_commands.describe(
    user="User to give Servant to",
    rank="Rank of the Servant",
    servant_name="Name of the Servant"
)
@app_commands.checks.has_permissions(administrator=True)
async def adminassign(
    interaction: discord.Interaction,
    user: discord.Member,
    rank: Literal["EX", "S", "A", "B", "C"],
    servant_name: str
):
    """Admin assign servant command"""
    if not await db.is_user_registered(user.id, interaction.guild.id):
        await interaction.response.send_message(
            f"❌ {user.mention} is not registered!",
            ephemeral=True
        )
        return
    
    servants = SERVANTS[rank]
    servant = next((s for s in servants if s['name'].lower() == servant_name.lower()), None)
    
    if not servant:
        await interaction.response.send_message(
            f"❌ Servant '{servant_name}' not found in rank {rank}!",
            ephemeral=True
        )
        return
    
    servant_id = await db.add_summon(user.id, interaction.guild.id, servant, rank)
    stats = await db.get_servant_stats(servant_id)
    
    await db.log_admin_action(
        interaction.guild.id,
        interaction.user.id,
        "assign_servant",
        user.id,
        f"Assigned {servant['name']} ({rank})"
    )
    
    embed = discord.Embed(
        title=f"{get_rarity_emoji(rank)} Servant Assigned",
        description=f"**{servant['name']}** has been assigned to {user.mention}!",
        color=get_enhanced_embed_color(rank)
    )
    
    embed.add_field(
        name="📊 Stats",
        value=f"⚔️ ATK: {stats['attack']} | 🛡️ DEF: {stats['defense']}\n"
              f"💗 HP: {stats['hp']} | ⚡ SPD: {stats['speed']}",
        inline=False
    )
    
    embed.set_footer(text=f"Granted by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="adminremove", description="[ADMIN] Remove a Servant from a user")
@app_commands.describe(user="User to remove Servant from")
@app_commands.checks.has_permissions(administrator=True)
async def adminremove(interaction: discord.Interaction, user: discord.Member):
    """Admin remove servant command"""
    summons = await db.get_user_summons(user.id, interaction.guild.id)
    
    if not summons:
        await interaction.response.send_message(
            f"❌ {user.mention} doesn't have any Servants!",
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
    role="Role to give registered users",
    channel="Channel to post registration message"
)
@app_commands.checks.has_permissions(administrator=True)
async def setupregistration(
    interaction: discord.Interaction,
    role: discord.Role,
    channel: discord.TextChannel
):
    """Setup registration command"""
    embed = discord.Embed(
        title="📜 MASTER REGISTRATION SYSTEM",
        description="Welcome to the Holy Grail War!\n\n"
                    "Register to become a Master and summon legendary Heroic Spirits!",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="✨ Benefits",
        value="• Summon legendary Servants\n"
              "• Participate in battles\n"
              "• Earn rewards daily\n"
              "• Complete missions",
        inline=False
    )
    
    embed.add_field(
        name="🎁 Starting Rewards",
        value="• 100 Saint Quartz\n"
              "• 3 Summon Tickets\n"
              "• 1 Free Summon",
        inline=False
    )
    
    embed.add_field(
        name="📝 Role Granted",
        value=role.mention,
        inline=True
    )
    
    embed.set_footer(text="Click the button below to register!")
    
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    
    view = RegistrationView()
    message = await channel.send(embed=embed, view=view)
    
    await db.set_registration_config(interaction.guild.id, role.id, channel.id, message.id)
    
    await db.log_admin_action(
        interaction.guild.id,
        interaction.user.id,
        "setup_registration",
        None,
        f"Set up registration in {channel.name}"
    )
    
    confirm_embed = discord.Embed(
        title="✅ Registration Setup Complete",
        description=f"Registration message posted in {channel.mention}",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=confirm_embed, ephemeral=True)

@bot.tree.command(name="adminlogs", description="[ADMIN] View recent admin actions")
@app_commands.checks.has_permissions(administrator=True)
async def adminlogs(interaction: discord.Interaction):
    """Admin logs command"""
    logs = await db.get_admin_logs(interaction.guild.id, 10)
    
    embed = discord.Embed(
        title="📋 Admin Action Logs",
        description="Recent admin actions",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    for log in logs:
        admin = interaction.guild.get_member(log['admin_id'])
        admin_name = admin.display_name if admin else f"ID:{log['admin_id']}"
        
        target = ""
        if log['target_user_id']:
            target_user = interaction.guild.get_member(log['target_user_id'])
            target = f" → {target_user.mention if target_user else f'ID:{log[\"target_user_id\"]}'}"
        
        timestamp = log['created_at'].strftime("%Y-%m-%d %H:%M")
        
        embed.add_field(
            name=f"{log['action_type'].replace('_', ' ').title()}",
            value=f"**By:** {admin_name}{target}\n"
                  f"**Details:** {log['details'] or 'N/A'}\n"
                  f"**Time:** {timestamp}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================================================
# INFO COMMANDS
# ============================================================================

@bot.tree.command(name="servantlist", description="View all available Servants by rank")
@app_commands.describe(rank="Rank to view")
async def servantlist(interaction: discord.Interaction, rank: Literal["EX", "S", "A", "B", "C"]):
    """Servant list command"""
    servants = SERVANTS[rank]
    
    embed = discord.Embed(
        title=f"{get_rank_emoji(rank)} {rank}-Rank Servants",
        description=f"All available Servants in the {rank} rank",
        color=get_enhanced_embed_color(rank),
        timestamp=datetime.now()
    )
    
    for servant in servants[:15]:  # Show max 15
        embed.add_field(
            name=f"{get_class_emoji(servant['class'])} {servant['name']}",
            value=f"**Class:** {servant['class']}\n"
                  f"**NP:** {servant['noble_phantasm']}\n"
                  f"*{servant['description'][:60]}...*",
            inline=False
        )
    
    if len(servants) > 15:
        embed.set_footer(text=f"Showing 15 of {len(servants)} servants")
    else:
        embed.set_footer(text=f"Total: {len(servants)} servants")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="View Holy Grail War statistics")
async def stats(interaction: discord.Interaction):
    """Stats command"""
    # Get guild stats
    elo_leaders = await db.get_elo_leaderboard(interaction.guild.id, 1)
    servant_leaders = await db.get_servant_leaderboard(interaction.guild.id, 1)
    
    embed = discord.Embed(
        title="📊 Holy Grail War Statistics",
        description=f"Server: **{interaction.guild.name}**",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    if elo_leaders:
        top_master = interaction.guild.get_member(elo_leaders[0]['user_id'])
        if top_master:
            embed.add_field(
                name="👑 Top Master",
                value=f"{top_master.mention}\n**ELO:** {elo_leaders[0]['elo_rating']}",
                inline=True
            )
    
    if servant_leaders:
        embed.add_field(
            name="⭐ Highest Level Servant",
            value=f"**{servant_leaders[0]['servant_name']}**\nLevel {servant_leaders[0]['level']}",
            inline=True
        )
    
    max_summons = await db.get_max_summons(interaction.guild.id)
    embed.add_field(
        name="📈 Max Summons",
        value=f"**{max_summons}** per user",
        inline=True
    )
    
    embed.set_footer(text="Use /leaderboard to see full rankings")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="View bot commands and features")
async def help_command(interaction: discord.Interaction):
    """Help command"""
    embed = discord.Embed(
        title="📖 Fate Bot Help",
        description="Welcome to the Holy Grail War bot!",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎴 Summoning",
        value="`/summon` - Summon a random Servant\n"
              "`/myservants` - View your Servants\n"
              "`/servantlist` - Browse available Servants",
        inline=False
    )
    
    embed.add_field(
        name="💰 Economy",
        value="`/daily` - Claim daily rewards\n"
              "`/balance` - Check your currency\n"
              "`/shop` - Browse items\n"
              "`/buy` - Purchase items\n"
              "`/inventory` - View your items\n"
              "`/equip` - Equip items to Servants",
        inline=False
    )
    
    embed.add_field(
        name="⚔️ Battle",
        value="`/battle` - Challenge another Master\n"
              "`/leaderboard` - View rankings",
        inline=False
    )
    
    embed.add_field(
        name="📋 Missions",
        value="`/missions` - View daily missions\n"
              "`/claimmission` - Claim mission rewards",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Information",
        value="`/stats` - View server statistics\n"
              "`/help` - Show this help message",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Admin Commands",
        value="`/setmaxsummons` - Set max Servants per user\n"
              "`/setbattleforum` - Set battle forum channel\n"
              "`/setupregistration` - Setup registration\n"
              "`/givecurrency` - Give currency to users\n"
              "`/adminassign` - Assign Servants to users\n"
              "`/adminremove` - Remove Servants from users\n"
              "`/adminlogs` - View admin action logs",
        inline=False
    )
    
    embed.set_footer(text="Good luck in the Holy Grail War, Master!")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@setmaxsummons.error
@adminassign.error
@adminremove.error
@setupregistration.error
@setbattleforum.error
@givecurrency.error
@adminlogs.error
async def admin_error(interaction: discord.Interaction, error):
    """Admin command error handler"""
    if isinstance(error, app_commands.errors.MissingPermissions):
        embed = discord.Embed(
            title="❌ Missing Permissions",
            description="You need Administrator permissions to use this command!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main function"""
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        raise ValueError("DISCORD_TOKEN environment variable not set")
    
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
