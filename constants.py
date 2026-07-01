ENTRY_TYPES = [
    "checkin",
    "diary_card",
    "skill_used",
    "thought_record",
    "abc",
    "behavioral_activation",
    "chain_analysis",
    "exposure_plan",
    "exposure_checkin",
    "journal",
]

ENTRY_TYPE_LABELS = {
    "checkin": "Emotion Check-In",
    "diary_card": "Diary Card",
    "skill_used": "Skill Used",
    "thought_record": "Thought Record",
    "abc": "ABC Worksheet",
    "behavioral_activation": "Behavioral Activation",
    "chain_analysis": "Chain Analysis",
    "exposure_plan": "Exposure",
    "exposure_checkin": "Exposure Check-In",
    "journal": "Journal",
}

DEFAULT_CATEGORY = "Emotion Regulation"

# Behavioral activation: track before/after levels for these emotions (1–10)
BEHAVIORAL_ACTIVATION_EMOTIONS = [
    {"key": "joy", "label": "Joy"},
    {"key": "sadness", "label": "Sadness"},
]

# Fixed emotions for diary card v1 (intensity 1–5 each)
DIARY_CARD_EMOTIONS = [
    "Anxious",
    "Sad",
    "Frustrated",
    "Content",
    "Grateful",
]

SKILL_MODULES = ["DT", "ER", "IE", "M"]

SKILL_MODULE_LABELS = {
    "DT": "Distress Tolerance",
    "ER": "Emotion Regulation",
    "IE": "Interpersonal Effectiveness",
    "M": "Mindfulness",
}

MODULE_SKILLS = {
    "DT": [
        "STOP",
        "TIPP (Temperature/Intense Exercise/Paced Breathing/Progressive Relaxation)",
        "Distract (ACCEPTS)",
        "Self-Soothe (5 senses)",
        "IMPROVE",
        "Radical Acceptance",
        "Willingness",
    ],
    "ER": [
        "PLEASE",
        "Opposite Action",
        "Check the Facts",
        "Accumulate Positives",
        "Build Mastery",
        "Cope Ahead",
        "Problem Solving",
    ],
    "IE": [
        "DEARMAN",
        "GIVE",
        "FAST",
    ],
    "M": [
        "Wise Mind",
        "Observe",
        "Describe",
        "Participate",
        "Non-judgmentally",
        "One-Mindfully",
        "Effectively",
    ],
}

# Emotion wheel families for multi-select UI
EMOTION_WHEEL = {
    "Joy": ["Happy", "Content", "Peaceful", "Hopeful", "Proud", "Grateful"],
    "Sadness": ["Sad", "Lonely", "Disappointed", "Grief", "Hurt", "Ashamed"],
    "Fear": ["Anxious", "Worried", "Scared", "Nervous", "Panicked", "Insecure"],
    "Anger": ["Angry", "Frustrated", "Irritated", "Resentful", "Jealous", "Enraged"],
    "Disgust": ["Disgusted", "Repulsed", "Contempt"],
    "Surprise": ["Surprised", "Confused", "Shocked"],
    "Other": ["Guilty", "Embarrassed", "Overwhelmed", "Numb", "Vulnerable"],
}

ALL_EMOTIONS = [e for emotions in EMOTION_WHEEL.values() for e in emotions]
