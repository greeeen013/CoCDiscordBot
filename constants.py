
import discord

# === Discord Channel IDs ===
WAR_INFO_CHANNEL_ID = 1366835944174391379
WAR_EVENTS_CHANNEL_ID = 1366835971395686554
LOG_CHANNEL_ID = 1371089891621998652
CAPITAL_STATUS_CHANNEL_ID = 1370467834932756600
PRAISE_CHANNEL_ID = 1371170358056452176
ADMIN_WARNING_CHANNEL_ID = 1371105995270393867
CLASH_OF_CLANS_EVENT_CHANNEL_ID = 1367054076688339053
VERIFICATION_CHANNEL_ID = 1366471838070476821
WELCOME_CHANNEL_ID = 1365768783083339878
RULES_CHANNEL_ID = 1366000196991062086
GENERAL_CHANNEL_ID = 1370722795826450452

# === Discord User/Role IDs ===
ADMIN_USER_ID = 317724566426222592
BOT_USER_ID = 1363529470778146876
VERIFICATION_ROLE_ID = 1372873720254955540

# === Event Emojis ===
EVENT_EMOJIS = {
    "Capital Gold": "<:capital_gold:1370839359896551677>",
    "Clan Capital": "<:clan_capital:1370710098158026792>",
    "Capital District": "<:capital_district:1370841273128456392>",
    "Capital Destroyed District": "<:capital_destroyed_district:1370843785688518706>",
    "Season End": "<:free_battlepass:1370713363188813865>",
    "CWL": "<:clan_war_league:1370712275614302309>",
    "Raid Weekend": "<:clan_capital:1370710098158026792>",
    "Trader Refresh": "<:trader:1370708896964022324>",
    "Clan Games": "<:clan_games:1370709757761028187>",
    "League Reset": "<:league_unranked:1365740650351558787>",
}

TOWN_HALL_EMOJIS = {
    17: "<:town_hall_17:1372327905882935467>",
    16: "<:town_hall_16:1372327703264497745>",
    15: "<:town_hall_15:1372327513975427183>",
    14: "<:town_hall_14:1372327272979103896>",
    13: "<:town_hall_13:1372259972053991434>",
    12: "<:town_hall_12:1372259837391405076>",
    11: "<:town_hall_11:1372259715840606449>",
    10: "<:town_hall_10:1372259547825307741>",
    9: "<:town_hall_9:1372259396842946671>",
    8: "<:town_hall_8:1372259356376170588>",
    7: "<:town_hall_7:1372259219302121522>"
} # Definování emoji pro jednotlivé úrovně Town Hall (TH) v Clash of Clans

HEROES_EMOJIS = {
    "Barbarian King": "<:barbarian_king:1371137125818568764>",
    "Archer Queen": "<:archer_queen:1371137339589394432>",
    "Grand Warden": "<:grand_warden:1371137633891254353>",
    "Royal Champion": "<:royal_champion:1371137975412592690>",
    "Minion Prince": "<:minion_prince:1371138182619463713>",
}

max_heroes_lvls = {
            10: {"Barbarian King": 40, "Archer Queen": 40, "Grand Warden": "N/A", "Royal Champion": "N/A",
                 "Minion Prince": 20},
            11: {"Barbarian King": 50, "Archer Queen": 50, "Grand Warden": 20, "Royal Champion": "N/A",
                 "Minion Prince": 30},
            12: {"Barbarian King": 65, "Archer Queen": 65, "Grand Warden": 40, "Royal Champion": "N/A",
                 "Minion Prince": 40},
            13: {"Barbarian King": 75, "Archer Queen": 75, "Grand Warden": 50, "Royal Champion": 25,
                 "Minion Prince": 50},
            14: {"Barbarian King": 80, "Archer Queen": 80, "Grand Warden": 55, "Royal Champion": 30,
                 "Minion Prince": 60},
            15: {"Barbarian King": 90, "Archer Queen": 90, "Grand Warden": 65, "Royal Champion": 45,
                 "Minion Prince": 70},
            16: {"Barbarian King": 95, "Archer Queen": 95, "Grand Warden": 70, "Royal Champion": 45,
                 "Minion Prince": "80"},
            17: {"Barbarian King": 100, "Archer Queen": 100, "Grand Warden": 75, "Royal Champion": 50,
                 "Minion Prince": "90"},
        }

# === Discord Role IDs ===
ROLE_VERIFIED = 1365768439473373235   # ověřený člen klanu
ROLE_ELDER    = 1366106980732633118   # Elder
ROLE_CO_LEADER= 1366106931042975845   # Co-Leader
ROLE_LEADER   = 1366106894816510062   # Leader
ROLES_STAFF   = (ROLE_CO_LEADER, ROLE_ELDER)

# Role ID pro Townhall levely
TOWNHALL_ROLES = {
    18: 1451935797434388550,
    17: 1365984171054469180,
    16: 1365984303535620148,
    15: 1365984329603354725,
    14: 1365984372406226994,
    13: 1365985135463370854,
    12: 1365984488185659423,
    11: 1365984518942621806,
}

# Role ID pro Ligy (Custom names)
LEAGUE_ROLES = {
    "Unranked": 1365984879405436978,
    "Skeleton 1": 1451932758351020264,
    "Skeleton 2": 1451932759307194552,
    "Skeleton 3": 1451932761865720039,
    "Barbarian 4": 1451932762989658155,
    "Barbarian 5": 1451932764445085778,
    "Barbarian 6": 1451932766534107259,
    "Archer 7": 1451932768085868644,
    "Archer 8": 1451932768891179080,
    "Archer 9": 1451932770443067393,
    "Wizard 10": 1451932771902816286,
    "Wizard 11": 1451932773223764018,
    "Wizard 12": 1451932774033391669,
    "Valkyrie 13": 1451932775648071690,
    "Valkyrie 14": 1451932777753608313,
    "Valkyrie 15": 1451932780484362323,
    "Witch 16": 1451932782619004941,
    "Witch 17": 1451932784510763008,
    "Witch 18": 1451932786217848865,
    "Golem 19": 1451932801141051588,
    "Golem 20": 1451932802491617342,
    "Golem 21": 1451932803439526104,
    "P.E.K.K.A 22": 1451932805171773550,
    "P.E.K.K.A 23": 1451932806598098994,
    "P.E.K.K.A 24": 1451932808368099462,
    "Titan 25": 1451932810217652296,
    "Titan 26": 1451932812272730275,
    "Titan 27": 1451932813505986673,
    "Dragon 28": 1451932815238238381,
    "Dragon 29": 1451932816807039069,
    "Dragon 30": 1451932817998090292,
    "Electro 31": 1451932819310772325,
    "Electro 32": 1451932820485439664,
    "Electro 33": 1451932822863614139,
    "Legend": 1451932825631723682,
}

LEAGUE_EMOJIS = {
    "league_unranked": "<:league_unranked:1451957963123200041>",
    "league_skeleton": "<:league_skeleton:1451956784897200241>",
    "league_barbarian": "<:league_barbarian:1451956787514314816>",
    "league_archer": "<:league_archer:1451956789967851660>",
    "league_wizard": "<:league_wizard:1451956791628796070>",
    "league_valkyrie": "<:league_valkyrie:1451956793621086279>",
    "league_witch": "<:league_witch:1451956795173109790>",
    "league_golem": "<:league_golem:1451956796435730484>",
    "league_pekka": "<:league_pekka:1451956798687805510>",
    "league_titan": "<:league_titan:1451957965429936239>",
    "league_dragon": "<:league_dragon:1451956800583630900>",
    "league_electro": "<:league_electro:1451956803503128708>",
    "league_legend": "<:league_legend:1451957967342665891>",
}

# Správa Leader/CoLeader/Admin (Elder) rolí
CLAN_ROLE_MAPPINGS = {
    "leader": ROLE_LEADER,
    "coleader": ROLE_CO_LEADER,
    "admin": ROLE_ELDER  # Admin = Elder v databázi
}

# ===== KONSTANTY PRO PETY =====
# Mapování TH na max Pet House level
TH_TO_PET_HOUSE = {
    14: 4,
    15: 8,
    16: 10,
    17: 11
}

# Max levely pro každý Pet podle úrovně Pet House
PET_MAX_LEVELS = {
    1: {"L.A.S.S.I": 10, "Electro Owl": 0, "Mighty Yak": 0, "Unicorn": 0, "Frosty": 0, "Diggy": 0,
        "Poison Lizard": 0, "Phoenix": 0, "Spirit Fox": 0, "Angry Jelly": 0, "Sneezy": 0},
    2: {"L.A.S.S.I": 10, "Electro Owl": 10, "Mighty Yak": 0, "Unicorn": 0, "Frosty": 0, "Diggy": 0,
        "Poison Lizard": 0, "Phoenix": 0, "Spirit Fox": 0, "Angry Jelly": 0, "Sneezy": 0},
    3: {"L.A.S.S.I": 10, "Electro Owl": 10, "Mighty Yak": 10, "Unicorn": 0, "Frosty": 0, "Diggy": 0,
        "Poison Lizard": 0, "Phoenix": 0, "Spirit Fox": 0, "Angry Jelly": 0, "Sneezy": 0},
    4: {"L.A.S.S.I": 10, "Electro Owl": 10, "Mighty Yak": 10, "Unicorn": 10, "Frosty": 0, "Diggy": 0,
        "Poison Lizard": 0, "Phoenix": 0, "Spirit Fox": 0, "Angry Jelly": 0, "Sneezy": 0},
    5: {"L.A.S.S.I": 15, "Electro Owl": 10, "Mighty Yak": 10, "Unicorn": 10, "Frosty": 10, "Diggy": 0,
        "Poison Lizard": 0, "Phoenix": 0, "Spirit Fox": 0, "Angry Jelly": 0, "Sneezy": 0},
    6: {"L.A.S.S.I": 15, "Electro Owl": 15, "Mighty Yak": 10, "Unicorn": 10, "Frosty": 10, "Diggy": 10,
        "Poison Lizard": 0, "Phoenix": 0, "Spirit Fox": 0, "Angry Jelly": 0, "Sneezy": 0},
    7: {"L.A.S.S.I": 15, "Electro Owl": 15, "Mighty Yak": 15, "Unicorn": 10, "Frosty": 10, "Diggy": 10,
        "Poison Lizard": 10, "Phoenix": 0, "Spirit Fox": 0, "Angry Jelly": 0, "Sneezy": 0},
    8: {"L.A.S.S.I": 15, "Electro Owl": 15, "Mighty Yak": 15, "Unicorn": 15, "Frosty": 10, "Diggy": 10,
        "Poison Lizard": 10, "Phoenix": 10, "Spirit Fox": 0, "Angry Jelly": 0, "Sneezy": 0},
    9: {"L.A.S.S.I": 15, "Electro Owl": 15, "Mighty Yak": 15, "Unicorn": 15, "Frosty": 15, "Diggy": 10,
        "Poison Lizard": 10, "Phoenix": 10, "Spirit Fox": 10, "Angry Jelly": 0, "Sneezy": 0},
    10: {"L.A.S.S.I": 15, "Electro Owl": 15, "Mighty Yak": 15, "Unicorn": 15, "Frosty": 15, "Diggy": 15,
         "Poison Lizard": 10, "Phoenix": 10, "Spirit Fox": 10, "Angry Jelly": 10, "Sneezy": 0},
    11: {"L.A.S.S.I": 15, "Electro Owl": 15, "Mighty Yak": 15, "Unicorn": 15, "Frosty": 15, "Diggy": 15,
         "Poison Lizard": 15, "Phoenix": 10, "Spirit Fox": 10, "Angry Jelly": 10, "Sneezy": 10}
}

EQUIPMENT_DATA = {
    1: {
        "unlock": "Earthquake Boots",
        "common": 9,
        "epic": 12,
        "th_required": 8
    },
    2: {
        "unlock": "Giant Arrow",
        "common": 9,
        "epic": 12,
        "th_required": 9
    },
    3: {
        "unlock": "Vampstache, Metal Pants",
        "common": 12,
        "epic": 15,
        "th_required": 10
    },
    4: {
        "unlock": "Rage Gem",
        "common": 12,
        "epic": 15,
        "th_required": 11
    },
    5: {
        "unlock": "Healer Puppet, Noble Iron",
        "common": 15,
        "epic": 18,
        "th_required": 12
    },
    6: {
        "unlock": "Healing Tome",
        "common": 15,
        "epic": 18,
        "th_required": 13
    },
    7: {
        "unlock": "Hog Rider Puppet",
        "common": 18,
        "epic": 21,
        "th_required": 14
    },
    8: {
        "unlock": "Haste Vial",
        "common": 18,
        "epic": 24,
        "th_required": 15
    },
    9: {
        "unlock": "Žádné nové (max level)",
        "common": 18,
        "epic": 27,
        "th_required": 16
    }
}

# Mapování TH na max Blacksmith level
TH_TO_BLACKSMITH = {
    8: 1,
    9: 2,
    10: 3,
    11: 4,
    12: 5,
    13: 6,
    14: 7,
    15: 8,
    16: 9,
    17: 9,  # TH17 má stejný max jako TH16
    18: 9 # TH18 má stejný max jako TH17
}

# ===== ZJEDNODUŠENÉ KONSTANTY PRO LABORATORY =====
TH_TO_LAB = {
    3: 1,
    4: 2,
    5: 3,
    6: 4,
    7: 5,
    8: 6,
    9: 7,
    10: 8,
    11: 9,
    12: 10,
    13: 11,
    14: 12,
    15: 13,
    16: 14,
    17: 15,
    18: 16
}

TROOP_UPGRADES = {
    # Elixir Troops
    "Barbarian": {1: 1, 3: 2, 5: 3, 7: 4, 8: 5, 9: 6, 10: 7, 11: 8, 12: 9, 14: 10, 15: 11, 16: 12},
    "Archer": {2: 1, 3: 2, 5: 3, 7: 4, 8: 5, 9: 6, 10: 7, 11: 8, 12: 9, 14: 10, 15: 11, 16: 12, 17: 13},
    "Giant": {3: 1, 4: 2, 6: 3, 7: 4, 8: 5, 9: 6, 10: 7, 11: 8, 12: 9, 13: 10, 15: 11, 16: 12, 17: 13},
    "Goblin": {2: 1, 3: 2, 5: 3, 7: 4, 8: 5, 9: 6, 10: 7, 12: 8, 15: 9},
    "Wall Breaker": {3: 1, 4: 2, 6: 3, 7: 4, 8: 5, 10: 6, 11: 7, 12: 8, 13: 9, 14: 10, 15: 11, 16: 12, 17: 13},
    "Balloon": {4: 2, 6: 3, 7: 4, 8: 5, 9: 6, 11: 7, 12: 8, 13: 9, 14: 10, 16: 11},
    "Wizard": {5: 2, 6: 3, 7: 4, 8: 5, 9: 6, 10: 7, 11: 8, 12: 9, 13: 10, 15: 11, 16: 12, 17: 13},
    "Healer": {7: 2, 8: 3, 9: 4, 11: 5, 13: 6, 14: 7, 15: 8, 16: 9, 17: 10},
    "Dragon": {7: 2, 8: 3, 9: 4, 10: 5, 11: 6, 12: 7, 13: 8, 14: 9, 15: 10, 16: 11, 17: 12},
    "P.E.K.K.A": {8: 3, 9: 4, 10: 6, 11: 7, 12: 8, 13: 9, 15: 10, 16: 11, 17: 12},
    "Baby Dragon": {9: 2, 10: 4, 11: 5, 12: 6, 13: 7, 14: 8, 15: 9, 16: 10, 17: 11},
    "Miner": {10: 3, 11: 5, 12: 6, 13: 7, 14: 8, 15: 9, 16: 10, 17: 11},
    "Electro Dragon": {11: 2, 12: 3, 13: 4, 14: 5, 15: 6, 16: 7, 17: 8},
    "Yeti": {12: 2, 13: 3, 14: 4, 15: 5, 16: 6, 17: 7},
    "Dragon Rider": {13: 2, 14: 3, 16: 4, 17: 5},
    "Electro Titan": {14: 2, 15: 3, 16: 4},
    "Root Rider": {15: 2, 16: 3},
    "Thrower": {16: 2, 17: 3},
    
    # Dark Elixir Troops
    "Minion": {7: 2, 8: 4, 9: 5, 10: 6, 11: 7, 12: 8, 13: 9, 14: 10, 15: 11, 16: 12, 17: 13},
    "Hog Rider": {7: 2, 8: 4, 9: 5, 10: 6, 11: 7, 12: 9, 13: 10, 14: 11, 15: 12, 16: 13, 17: 14},
    "Valkyrie": {8: 2, 9: 4, 10: 5, 11: 6, 12: 7, 13: 8, 14: 9, 15: 10, 16: 11},
    "Golem": {8: 2, 9: 4, 10: 5, 11: 7, 12: 9, 13: 10, 14: 11, 15: 12, 16: 13, 17: 14},
    "Witch": {9: 2, 10: 3, 11: 4, 12: 5, 15: 6, 16: 7},
    "Lava Hound": {9: 2, 10: 3, 11: 4, 12: 5, 13: 6},
    "Bowler": {10: 2, 11: 3, 12: 4, 13: 5, 14: 6, 15: 7, 16: 8, 17: 9},
    "Ice Golem": {11: 3, 12: 5, 14: 6, 15: 7, 16: 8, 17: 9},
    "Headhunter": {12: 2, 13: 3},
    "Apprentice Warden": {13: 2, 14: 3, 15: 4},
    "Druid": {14: 2, 15: 3, 16: 4}
}

SIEGE_MACHINE_UPGRADES = {
    "Wall Wrecker": {
        10: (2, 3),
        11: 4,
        13: 5
    },
    "Battle Blimp": {
        10: (2, 3),
        11: 4,
        13: 5
    },
    "Stone Slammer": {
        10: (2, 3),
        11: 4,
        13: 5
    },
    "Siege Barracks": {
        10: (2, 3),
        11: 4,
        14: 5
    },
    "Log Launcher": {
        10: (2, 3),
        11: 4,
        14: 5
    },
    "Flame Flinger": {
        10: (2, 3),
        11: 4,
        14: 5
    },
    "Battle Drill": {
        13: (2, 3, 4),
        15: 5
    },
    "Troop Launcher": {
        14: (2, 3),
        15: 4
    }
}

SPELL_UPGRADES = {
    # Elixir Spells
    "Lightning Spell": {3: 2, 4: 3, 5: 4, 6: 4, 7: 4, 8: 5, 9: 6, 10: 7, 11: 8, 12: 9, 13: 9, 14: 9, 15: 10, 16: 11, 17: 12},
    "Healing Spell": {4: 2, 5: 2, 6: 3, 7: 4, 8: 5, 9: 6, 10: 7, 11: 7, 12: 7, 13: 8, 14: 8, 15: 9, 16: 10, 17: 11},
    "Rage Spell": {5: 2, 6: 3, 7: 4, 8: 5, 9: 5, 10: 5, 11: 5, 12: 6, 13: 6, 14: 6, 15: 6, 16: 6, 17: 6},
    "Jump Spell": {7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 12: 3, 13: 4, 14: 4, 15: 5, 16: 5, 17: 5},
    "Freeze Spell": {9: 2, 10: 5, 11: 6, 12: 7, 13: 7, 14: 7, 15: 7, 16: 7, 17: 7},
    "Clone Spell": {10: 3, 11: 5, 12: 5, 13: 6, 14: 7, 15: 8, 16: 8, 17: 8},
    "Invisibility Spell": {11: 2, 12: 3, 13: 4, 14: 4, 15: 4, 16: 4, 17: 4},
    "Recall Spell": {13: 2, 14: 3, 15: 4, 16: 5, 17: 6},
    "Revive Spell": {15: 2, 16: 3, 17: 4},

    # Dark Spells
    "Poison Spell": {8: 2, 9: 3, 10: 4, 11: 5, 12: 6, 13: 7, 14: 8, 15: 9, 16: 10, 17: 11},
    "Earthquake Spell": {8: 2, 9: 3, 10: 4, 11: 5, 12: 5, 13: 5, 14: 5, 15: 5, 16: 5, 17: 5},
    "Haste Spell": {9: 2, 10: 4, 11: 5, 12: 5, 13: 5, 14: 5, 15: 5, 16: 5, 17: 6},
    "Skeleton Spell": {10: 3, 11: 4, 12: 6, 13: 7, 14: 7, 15: 8, 16: 8, 17: 8},
    "Bat Spell": {10: 3, 11: 4, 12: 5, 13: 5, 14: 5, 15: 6, 16: 6, 17: 7},
    "Overgrowth Spell": {12: 2, 13: 2, 14: 3, 15: 3, 16: 4, 17: 4}
}
