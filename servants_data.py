import discord

# All Fate series Servants organized by canonical power scaling
SERVANTS = {
    "EX": [
        {"name": "Gilgamesh", "class": "Archer", "description": "The King of Heroes, possessor of all the world's treasures", "noble_phantasm": "Gate of Babylon", "image_url": None},
        {"name": "Artoria Pendragon (Lancer Alter)", "class": "Lancer", "description": "The corrupted Lion King wielding Rhongomyniad", "noble_phantasm": "Rhongomyniad", "image_url": None},
        {"name": "Karna", "class": "Lancer", "description": "Son of the Sun God, Hero of Charity with impenetrable golden armor", "noble_phantasm": "Vasavi Shakti", "image_url": None},
        {"name": "Enkidu", "class": "Lancer", "description": "The Chain of Heaven, created by the gods as Gilgamesh's equal", "noble_phantasm": "Enuma Elish", "image_url": None},
        {"name": "Solomon", "class": "Caster", "description": "King of Magic, the original Grand Caster", "noble_phantasm": "Ars Nova", "image_url": None},
        {"name": "Merlin", "class": "Caster", "description": "The Magus of Flowers, a half-incubus mage of Arthurian legend", "noble_phantasm": "Garden of Avalon", "image_url": None},
        {"name": "Romulus-Quirinus", "class": "Lancer", "description": "The deified founder of Rome, embodiment of Rome itself", "noble_phantasm": "Per Aspera Ad Astra", "image_url": None},
        {"name": "Super Orion", "class": "Archer", "description": "The ultimate hunter, manifestation of Orion at his peak", "noble_phantasm": "Artemis Agnos", "image_url": None},
        {"name": "Morgan le Fay", "class": "Berserker", "description": "The witch-queen, ruler of fairy Britain", "noble_phantasm": "Roadless Camelot", "image_url": None},
    ],
    "S": [
        {"name": "Artoria Pendragon", "class": "Saber", "description": "The Once and Future King, wielder of the holy sword Excalibur", "noble_phantasm": "Excalibur", "image_url": None},
        {"name": "Achilles", "class": "Rider", "description": "The invincible hero of the Trojan War", "noble_phantasm": "Troias Tragōidia", "image_url": None},
        {"name": "Heracles", "class": "Berserker", "description": "The greatest Greek hero who completed twelve labors", "noble_phantasm": "Nine Lives", "image_url": None},
        {"name": "Ozymandias", "class": "Rider", "description": "King of Kings, the Sun King Ramesses II of Egypt", "noble_phantasm": "Ramesseum Tentyris", "image_url": None},
        {"name": "Scáthach", "class": "Lancer", "description": "The immortal warrior-queen of the Land of Shadows", "noble_phantasm": "Gáe Bolg Alternative", "image_url": None},
        {"name": "Cu Chulainn (Alter)", "class": "Berserker", "description": "The corrupted Hound of Ulster, a beast of pure madness", "noble_phantasm": "Curruid Coinchenn", "image_url": None},
        {"name": "Iskandar", "class": "Rider", "description": "Alexander the Great, King of Conquerors", "noble_phantasm": "Ionioi Hetairoi", "image_url": None},
        {"name": "Arjuna (Alter)", "class": "Berserker", "description": "The God-Slaying Hero who absorbed the Hindu Pantheon", "noble_phantasm": "Mahāpralaya", "image_url": None},
        {"name": "Jeanne d'Arc", "class": "Ruler", "description": "The Holy Maiden of Orleans, bearer of God's revelation", "noble_phantasm": "Luminosité Eternelle", "image_url": None},
        {"name": "Richard I", "class": "Saber", "description": "Richard the Lionheart, the legendary crusader king of England", "noble_phantasm": "Excalibur", "image_url": None},
        {"name": "Quetzalcoatl", "class": "Rider", "description": "The Aztec feathered serpent goddess of the sun", "noble_phantasm": "Xiuhcoatl", "image_url": None},
        {"name": "First Hassan", "class": "Assassin", "description": "The original Hassan-i-Sabbah, Grand Assassin", "noble_phantasm": "Azrael", "image_url": None},
        {"name": "Sigurd", "class": "Saber", "description": "The supreme dragon-slayer of Norse legend", "noble_phantasm": "Gram", "image_url": None},
        {"name": "Brynhildr", "class": "Lancer", "description": "The Valkyrie queen who loved Sigurd", "noble_phantasm": "Brynhildr Romantia", "image_url": None},
    ],
    "A": [
        {"name": "Mordred", "class": "Saber", "description": "The traitorous knight who brought down Camelot", "noble_phantasm": "Clarent Blood Arthur", "image_url": None},
        {"name": "Lancelot", "class": "Berserker", "description": "The Knight of the Lake, greatest of the Round Table", "noble_phantasm": "Arondight", "image_url": None},
        {"name": "Siegfried", "class": "Saber", "description": "Dragon-Blooded Knight with an invincible body", "noble_phantasm": "Balmung", "image_url": None},
        {"name": "Cu Chulainn", "class": "Lancer", "description": "The Hound of Ulster, legendary Irish hero", "noble_phantasm": "Gáe Bolg", "image_url": None},
        {"name": "Ishtar", "class": "Archer", "description": "Mesopotamian Goddess of Beauty and War", "noble_phantasm": "An Gal Tā Kigal Shē", "image_url": None},
        {"name": "Vlad III", "class": "Lancer", "description": "Vlad the Impaler, defender of his homeland Romania", "noble_phantasm": "Kazikli Bey", "image_url": None},
        {"name": "Francis Drake", "class": "Rider", "description": "The legendary privateer who circumnavigated the globe", "noble_phantasm": "Golden Wild Hunt", "image_url": None},
        {"name": "Okita Souji", "class": "Saber", "description": "Captain of the Shinsengumi's First Unit", "noble_phantasm": "Mumyou Sandanzuki", "image_url": None},
        {"name": "Miyamoto Musashi", "class": "Saber", "description": "Japan's greatest swordsman, master of two heavens", "noble_phantasm": "Niten Ichiryu", "image_url": None},
        {"name": "Oda Nobunaga", "class": "Archer", "description": "The Demon King of the Sixth Heaven", "noble_phantasm": "Three Thousand Worlds", "image_url": None},
        {"name": "Kintoki", "class": "Berserker", "description": "The golden boy of Mount Ashigara", "noble_phantasm": "Golden Spark", "image_url": None},
        {"name": "Minamoto no Raikou", "class": "Berserker", "description": "The head of the Four Heavenly Kings", "noble_phantasm": "Ox-King Storm Call", "image_url": None},
        {"name": "Altria Pendragon (Alter)", "class": "Saber", "description": "The corrupted King of Knights", "noble_phantasm": "Excalibur Morgan", "image_url": None},
        {"name": "Mysterious Heroine X", "class": "Assassin", "description": "A Saber-hunting assassin from the Servantverse", "noble_phantasm": "Secret-Calibur", "image_url": None},
        {"name": "Gawain", "class": "Saber", "description": "The Knight of the Sun, Artoria's nephew", "noble_phantasm": "Excalibur Galatine", "image_url": None},
        {"name": "Tristan", "class": "Archer", "description": "The Knight of Lamentation from the Round Table", "noble_phantasm": "Failnaught", "image_url": None},
        {"name": "Bedivere", "class": "Saber", "description": "The last knight to serve King Arthur", "noble_phantasm": "Switch On - Airgetlám", "image_url": None},
    ],
    "B": [
        {"name": "Emiya", "class": "Archer", "description": "The nameless hero, a Counter Guardian from an erased future", "noble_phantasm": "Unlimited Blade Works", "image_url": None},
        {"name": "Medusa", "class": "Rider", "description": "The Gorgon, possessing Mystic Eyes of Petrification", "noble_phantasm": "Bellerophon", "image_url": None},
        {"name": "Diarmuid Ua Duibhne", "class": "Lancer", "description": "First warrior of the knights of Fianna", "noble_phantasm": "Gáe Dearg & Gáe Buidhe", "image_url": None},
        {"name": "Gilles de Rais", "class": "Caster", "description": "Bluebeard, the mad marshal of France", "noble_phantasm": "Prelati's Spellbook", "image_url": None},
        {"name": "Medea", "class": "Caster", "description": "The Witch of Betrayal from Colchis", "noble_phantasm": "Rule Breaker", "image_url": None},
        {"name": "Hassan of the Cursed Arm", "class": "Assassin", "description": "One of the nineteen Hassan-i-Sabbah", "noble_phantasm": "Zabaniya", "image_url": None},
        {"name": "Atalanta", "class": "Archer", "description": "The chaste huntress of Greek legend", "noble_phantasm": "Phoebus Catastrophe", "image_url": None},
        {"name": "Frankenstein", "class": "Berserker", "description": "The tragic monster created by Victor Frankenstein", "noble_phantasm": "Blasted Tree", "image_url": None},
        {"name": "Tamamo-no-Mae", "class": "Caster", "description": "The nine-tailed fox of Japanese legend", "noble_phantasm": "Eightfold Blessing", "image_url": None},
        {"name": "Nero Claudius", "class": "Saber", "description": "The Red Saber, tyrant emperor of Rome", "noble_phantasm": "Aestus Domus Aurea", "image_url": None},
        {"name": "Elizabeth Bathory", "class": "Lancer", "description": "The blood countess, an idol-loving dragon", "noble_phantasm": "Kilenc Sárkány", "image_url": None},
        {"name": "Robin Hood", "class": "Archer", "description": "The heroic outlaw of Sherwood Forest", "noble_phantasm": "Yew Bow", "image_url": None},
        {"name": "Cursed Arm Hassan", "class": "Assassin", "description": "An assassin who obtained Shaytan's arm", "noble_phantasm": "Zabaniya", "image_url": None},
        {"name": "David", "class": "Archer", "description": "The shepherd king who slew Goliath", "noble_phantasm": "Hamesh Avanim", "image_url": None},
        {"name": "Hektor", "class": "Lancer", "description": "The greatest warrior of Troy", "noble_phantasm": "Durindana", "image_url": None},
        {"name": "Leonidas", "class": "Lancer", "description": "The Spartan king who defended Thermopylae", "noble_phantasm": "Thermopylae Enomotia", "image_url": None},
        {"name": "Rama", "class": "Saber", "description": "The seventh avatar of Vishnu", "noble_phantasm": "Brahmastra", "image_url": None},
        {"name": "Li Shuwen", "class": "Lancer", "description": "The martial artist who killed with a single strike", "noble_phantasm": "Shen Qiang Wu Er Da", "image_url": None},
        {"name": "Beowulf", "class": "Berserker", "description": "The legendary Geatish hero who slew Grendel", "noble_phantasm": "Grendel Buster", "image_url": None},
        {"name": "Paracelsus", "class": "Caster", "description": "The founder of toxicology and physician", "noble_phantasm": "Sword of Paracelsus", "image_url": None},
    ],
    "C": [
        {"name": "Sasaki Kojirou", "class": "Assassin", "description": "The nameless samurai who achieved the pinnacle of swordsmanship", "noble_phantasm": "Tsubame Gaeshi", "image_url": None},
        {"name": "Hans Christian Andersen", "class": "Caster", "description": "The cynical author of fairy tales", "noble_phantasm": "Märchen Meines Lebens", "image_url": None},
        {"name": "William Shakespeare", "class": "Caster", "description": "The playwright who observes all of humanity", "noble_phantasm": "First Folio", "image_url": None},
        {"name": "Mata Hari", "class": "Assassin", "description": "The exotic dancer and spy of World War I", "noble_phantasm": "Mata Hari", "image_url": None},
        {"name": "Phantom of the Opera", "class": "Assassin", "description": "The tragic ghost of the Paris Opera House", "noble_phantasm": "Christine, Christine", "image_url": None},
        {"name": "Spartacus", "class": "Berserker", "description": "The gladiator who led the slave rebellion", "noble_phantasm": "Crying Warmonger", "image_url": None},
        {"name": "Caligula", "class": "Berserker", "description": "The mad Roman emperor", "noble_phantasm": "Flucticulus Diana", "image_url": None},
        {"name": "Boudica", "class": "Rider", "description": "Queen of Victory who fought against Rome", "noble_phantasm": "Chariot of Boudica", "image_url": None},
        {"name": "Lu Bu", "class": "Berserker", "description": "The Flying General of the Three Kingdoms", "noble_phantasm": "God Force", "image_url": None},
        {"name": "Jing Ke", "class": "Assassin", "description": "The failed assassin of the First Emperor", "noble_phantasm": "Non-Reflective Blade", "image_url": None},
        {"name": "Darius III", "class": "Berserker", "description": "The last Achaemenid king of Persia", "noble_phantasm": "Athanaton Ten Thousand", "image_url": None},
        {"name": "Charles Babbage", "class": "Caster", "description": "The father of the computer", "noble_phantasm": "Dimension of Steam", "image_url": None},
        {"name": "Geronimo", "class": "Caster", "description": "The legendary Apache warrior and shaman", "noble_phantasm": "Tsago Degi Naleya", "image_url": None},
        {"name": "Billy the Kid", "class": "Archer", "description": "The young gunslinger of the Wild West", "noble_phantasm": "Thunderer", "image_url": None},
        {"name": "Mephistopheles", "class": "Caster", "description": "The demon of Faust's legend", "noble_phantasm": "Ticktock Bomb", "image_url": None},
        {"name": "Eric Bloodaxe", "class": "Berserker", "description": "The Norwegian king and Viking", "noble_phantasm": "Bloodbath Crown", "image_url": None},
        {"name": "Angra Mainyu", "class": "Avenger", "description": "All the World's Evil, the weakest servant", "noble_phantasm": "Verg Avesta", "image_url": None},
        {"name": "Phantom", "class": "Assassin", "description": "The phantom of the opera", "noble_phantasm": "Christine, Christine", "image_url": None},
        {"name": "Sanson", "class": "Assassin", "description": "The royal executioner of France", "noble_phantasm": "La Mort Espoir", "image_url": None},
        {"name": "Hundred Faced Hassan", "class": "Assassin", "description": "Hassan with split personalities", "noble_phantasm": "Zabaniya", "image_url": None},
    ],
}

def get_rank_color(rank: str) -> discord.Color:
    """Get the color associated with a rank"""
    colors = {
        "EX": discord.Color.from_rgb(255, 215, 0),  # Gold
        "S": discord.Color.from_rgb(220, 20, 60),   # Crimson
        "A": discord.Color.from_rgb(147, 112, 219), # Medium Purple
        "B": discord.Color.from_rgb(65, 105, 225),  # Royal Blue
        "C": discord.Color.from_rgb(144, 238, 144), # Light Green
    }
    return colors.get(rank, discord.Color.greyple())

def get_rank_emoji(rank: str) -> str:
    """Get the emoji associated with a rank"""
    emojis = {
        "EX": "⭐",
        "S": "💎",
        "A": "🔷",
        "B": "🔹",
        "C": "⚪",
    }
    return emojis.get(rank, "❓")

def get_class_emoji(servant_class: str) -> str:
    """Get the emoji associated with a servant class"""
    class_emojis = {
        "Saber": "⚔️",
        "Archer": "🏹",
        "Lancer": "🔱",
        "Rider": "🐎",
        "Caster": "📖",
        "Assassin": "🗡️",
        "Berserker": "💢",
        "Ruler": "⚖️",
        "Avenger": "😈",
        "Alter Ego": "👥",
        "Foreigner": "🌌",
        "Shielder": "🛡️",
    }
    return class_emojis.get(servant_class, "❓")

def get_all_servants():
    """Get all servants across all ranks"""
    all_servants = []
    for rank, servants in SERVANTS.items():
        for servant in servants:
            servant_copy = servant.copy()
            servant_copy['rank'] = rank
            all_servants.append(servant_copy)
    return all_servants

def search_servant(name: str):
    """Search for a servant by name"""
    name_lower = name.lower()
    for rank, servants in SERVANTS.items():
        for servant in servants:
            if name_lower in servant['name'].lower():
                servant_copy = servant.copy()
                servant_copy['rank'] = rank
                return servant_copy
    return None

def get_servants_by_class(servant_class: str):
    """Get all servants of a specific class"""
    result = []
    for rank, servants in SERVANTS.items():
        for servant in servants:
            if servant['class'].lower() == servant_class.lower():
                servant_copy = servant.copy()
                servant_copy['rank'] = rank
                result.append(servant_copy)
    return result

def get_rank_stats():
    """Get statistics about servants per rank"""
    return {
        rank: len(servants) 
        for rank, servants in SERVANTS.items()
    }
