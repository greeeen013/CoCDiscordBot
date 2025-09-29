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
