
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


# Správa Leader/CoLeader/Admin (Elder) rolí
CLAN_ROLE_MAPPINGS = {
    "leader": ROLE_LEADER,
    "coleader": ROLE_CO_LEADER,
    "admin": ROLE_ELDER  # Admin = Elder v databázi
}
