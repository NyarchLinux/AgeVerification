# questions.py
#
# The single place to edit the quiz.
#
# Question schema
# ---------------
#   {
#     "image": <str|None>,   # optional question image (asset filename under src/assets/)
#     "text":  <str>,        # question text
#     "options": [           # exactly 4 options -> A, B, C, D
#       {
#         "image":      <str|None>,                  # optional option image
#         "text":       <str|None>,                  # optional text (image-only
#                                                   # options are allowed)
#         "age":        <int>,                       # mean age of who picks this
#         "weight":     <float>,                     # confidence weight
#         "transition": {"message": <str>,
#                        "image":  <str|None>,     # optional image shown for 3s
#                        "sound":  <str|None>},    # optional sound effect (asset
#                                                   # filename under src/assets/).
#                                                   # None -> default jingle.
#       },
#       ...
#     ],
#   }
#
# Add / remove / reorder questions freely. The first option becomes "A", etc.

QUESTIONS = [
    {
        "image": None,
        "text": "Which number do you prefer",
        "options": [
            {"image": None, "text": "67",       "age": 5, "weight": 0.8,
             "transition": {"message": "ha ha how funny.", "image": "baby.jpg", "sound": "among.mp3"}},
            {"image": None, "text": "69",       "age": 24, "weight": 0.2,
             "transition": {"message": "Nice.", "image": "nice.png", "sound": "nice.mp3"}},
            {"image": None, "text": "gugugaga", "age": 1,  "weight": 1.0,
             "transition": {"message": "Interesting...",
                            "image": "baby.jpg", "sound": "among.mp3"}},
            {"image": None, "text": "420",       "age": 30, "weight": 0.3,
             "transition": {"message": "Huh", "image": "thinking.png", "sound": "among.mp3"}},
        ],
    },
    {
        "image": None,
        "text": "Which meme do you prefer",
        "options": [
            {"image": "minion.jpg", "text": "",    "age": 60, "weight": 1.0,
             "transition": {"message": "Yeah funny", "image": "thumbup.png"}},
            {"image": "ae.png", "text": "",     "age": 24, "weight": 0.6,
             "transition": {"message": "Not very popular, I see...", "image": "thinking.png"}},
            {"image": "skibidi.jpg", "text": "", "age": 3, "weight": 1.0,
             "transition": {"message": "Skibidi sigma.", "image": "skibidi.jpg", "sound": "skibidi.mp3"}},
            {"image": "firstememe.jpg", "text": None, "age": 100, "weight": 1.0,
             "transition": {"message": "You must be an og", "image": "granny.png"}},
        ],
    },
    {
        "image": None,
        "text": "Which one of these photos looks more like you",
        "options": [
            {"image": "ajanokoji.jpg",    "age": 12, "weight": 3.0,
             "transition": {"message": "You must have learned dark psychology at a young age", "image": "psy.jpg"}},
            {"image": "ryan.jpg", "age": 30, "weight": 2.0,
             "transition": {"message": "Literally me!!", "image": "ryan.jpg"}},
            {"image": "trump.jpg", "text": None, "age": 80, "weight": 2.0,
             "transition": {"message": "Make america great again! (maybe)", "image": "trump.jpg"}},
            {"image": "baby.jpg", "text": None,         "age": 1,  "weight": 3.0,
             "transition": {"message": "Ohhh so you look like that...", "image": "thinking.png", "sound": "sus.mp3"}},
        ],
    },
    {
        "image": None,
        "text": "Which UI looks better",
        "options": [
            {"image": "macos.png",        "age": 3, "weight": 0.2,
             "transition": {"message": "Mhmm.", "image": "thinking.png"}},
            {"image": "nyarch.png", "text": None,       "age": 19, "weight": 0.4,
             "transition": {"message": "I use Nyarch btw.", "image": "nice.png"}},
            {"image": "lunduke.png", "text": None,    "age": 45, "weight": 1.0,
             "transition": {"message": "Retro computing journalist energy.", "image": "thinking.png", "sound": "lund.mp3"}},
            {"image": "winzoz.jpg","age": 30, "weight": 1.0,
             "transition": {"message": "Aero Glass enjoyer.", "image": "thinking.png"}},
        ],
    },
    {
        "image": None,
        "text": "If you were to search something, what would you use",
        "options": [
            {"image": "google.png", "text": "Google",       "age": 30, "weight": 0.3,
             "transition": {"message": "Reliable, boring, gets the job done.", "image": "thinking.png"}},
            {"image": "tiktok.png", "text": "TikTok",       "age": 15, "weight": 1.5,
             "transition": {"message": "Damn you are brainrotted.", "image": "thinking.png", "sound": "sus.mp3"}},
            {"image": "h.jpg", "text": "The big HH",  "age": 24, "weight": 1.8,
             "transition": {"message": "A man/woman/something of culture, I see", "sound": "ahh.mp3", "image": "thinking.png"}},
            {"image": None, "text": "Ask Mommy",    "age": 6,  "weight": 3.0,
             "transition": {"message": "MOMMY!!! WHERE'S THE IPAD?!", "image": "baby.jpg", "sound": "sus.mp3"}},
        ],
    },
    {
        "image": None,
        "text": "How many books have you read in your life",
        "options": [
            {"image": None, "text": "Between 2 and 5",  "age": 18, "weight": 0.5,
             "transition": {"message": "Ouch", "image": "thinking.png"}},
            {"image": None, "text": "Big flat 0",       "age": 3,  "weight": 2.0,
             "transition": {"message": "I see, who needs books when there is brainrot", "image": "thinking.png", "sound": "sus.mp3"}},
            {"image": None, "text": "Between 5 and 20", "age": 28, "weight": 1.0,

             "transition": {"message": "Bro the fuck just use the internet.", "image": "thinking.png"}},
            {"image": None, "text": "More than 20",     "age": 55, "weight": 2.0,
             "transition": {"message": "Dark romance doesn't count.", "image": "thinking.png"}},
        ],
    },
    {
        "image": None,
        "text": "When did Covid happen",
        "options": [
            {"image": None, "text": "idk I was not born", "age": 4,  "weight": 2.0,
             "transition": {"message": "You are fresh. So fresh.",
                            "image": "baby.jpg", "sound": "sus.mp3"}},
            {"image": None, "text": "2020",               "age": 25, "weight": 1.0,
             "transition": {"message": "Yeah makes sense", "image": "thumbup.png"}},
            {"image": None, "text": "2033 and 2020",      "age": -23, "weight": 8.0,
             "transition": {"message": "A time traveler duh", "image": "thinking.png"}},
            {"image": None, "text": "Never happened",     "age": 70, "weight": 1.0,
             "transition": {"message": "Yeah it was everything to put 5G in our veins", "image": "thinking.png", "sound": "sus.mp3"}},
        ],
    },
    {
        "image": None,
        "text": "Which anime do you prefer",
        "options": [
            {"image": None, "text": "Katsudō Shashin", "age": 90, "weight": 1.0,
             "transition": {"message": "Must have been fun times.", "image": "granny.png"}},
            {"image": None, "text": "JoJo",            "age": 27, "weight": 1.3,
             "transition": {"message": "You expected a transition screen but it was me, DIO!", "image": "dio.jpg"}},
            {"image": None, "text": "Attack on Titan", "age": 17, "weight": 0.8,
             "transition": {"message": "Code Geass is better tbh", "image": "thinking.png"}},
            {"image": None, "text": "Solo Leveling",   "age": 10, "weight": 2.0,
             "transition": {"message": "Aura > Plot apparently", "image": "sololev.jpg", "sound": "auraa.mp3"}},
        ],
    },
    {
        "image": None,
        "text": "Which operating system do you prefer",
        "options": [
            {"image": None, "text": "Nyarch",    "age": 19, "weight": 1.0,
             "transition": {"message": "I use Nyarch btw.", "image": "nice.png"}},
            {"image": None, "text": "iPadOS",    "age": 4, "weight": 2.0,
             "transition": {"message": "Huh I see, a nice screen to watch skibidi", "image": None}},
            {"image": None, "text": "Windows 7", "age": 40, "weight": 2.0,
             "transition": {"message": "The last good Windows. We weep for it.", "image": None}},
            {"image": None, "text": "MS-DOS",    "age": 75, "weight": 1.0,
             "transition": {"message": "C:\\>_  You typed your first letter this way.", "image": None}},
        ],
    },
    {
        "image": None,
        "text": "Which game do you prefer",
        "options": [
            {"image": None, "text": "Minecraft",   "age": 22, "weight": 2.0,
             "transition": {"message": "Peakest game in history.", "image": None}},
            {"image": None, "text": "Roblox",      "age": 8, "weight": 3.0,
             "transition": {"message": "Oof.", "image": "roblox.jpg", "sound": "oof.mp3"}},
            {"image": None, "text": "Candy Crush", "age": 60, "weight": 3.0,
             "transition": {"message": "Just one more level, then bed. (Narrator: there were more.)", "image": None}},
            {"image": None, "text": "Hoop rolling", "age": 85, "weight": 3.0,
             "transition": {"message": "The best ones are the simplest", "image": None}},
        ],
    },
]

# ---- tweakable knobs ---------------------------------------------------

# Subway Surfers discount: -1 year per SUBWAY_SECS_PER_YEAR seconds watched.
#   10s watched -> -1 year, 20s -> -2 years, 100s -> -10 years, etc.
# Capped at SUBWAY_MAX_DISCOUNT years.
SUBWAY_SECS_PER_YEAR = 10     # seconds of watching = 1 year off
SUBWAY_MAX_DISCOUNT = 10      # maximum years removed

# AI evaluation screen (Spec 5): progress bar over ~10-15s, rotating subtitles.
EVAL_DURATION_SEC = 12
EVAL_SUBTITLE_INTERVAL_SEC = 4.5
EVAL_SUBTITLES = [
    "Doing linear racism…",
    "Brainrotting the neural net…",
    "Watching some reels…",
    "Checking your history in the last 30 days…",
    "Comparing stolen data…",
    "Min-maxing your birth year…",
    "Contacting OpenAI servers to find out…",
    "Applying Racism Forest...",
    "Taking a photo of you face…",
    "Preparing the next reel to make you see to vote my party…",
]

# ---- result categories -------------------------------------------------

def age_category(age: int) -> str:
    """Map a final age to a fun little label."""
    if age < 8:
        return "OK Ipad Kid skibidi next time 🍼"
    if age < 16:
        return "Nice try, wait a few years"
    if age < 18:
        return "I'm bricking your PC for a couple of years, bye 💀"
    if age < 28:
        return "Here you go welcome to Nyarch 😎"
    if age < 45:
        return "Age ok have fun 🥑"
    if age < 70:
        return "Ok Boomer 📺"
    return "Elder of the Internet 🧙"
