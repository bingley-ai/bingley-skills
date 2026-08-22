"""brain_maps — per-skill mapping DATA (no code).

This is the ONE place a skill's fields are mapped to brain paths. The generic bridge
(`brain_bridge.py`) reads these tables; adding a skill in M4 = add an entry here, nothing else.

Each entry:
  profile : skill field -> brain path   (business facts + capture flags)
  lens    : skill field -> brain path   (preferences), or {} if the skill has no lens
  force   : skill fields that are OPERATIONAL state (always applied, never precedence-rejected)
  legacy_profile : legacy JSON filename whose keys are this skill's profile fields (read-only
                   fallback during transition), or None
  legacy_lens    : legacy lens JSON filename, value-classified (B2B/B2C, A/B, mode), or None

Defaults are NOT stored here — they are derived from schema.py (single source of truth).
"""

SKILLS = {
    "cold-email": {
        "profile": {
            "name": "business.name", "product": "business.product", "audience": "business.audience",
            "problem": "business.problem", "proof": "business.proof", "ask": "business.ask",
            "seen": "capture.seen", "deepDone": "capture.deepDone", "deepSkips": "capture.deepSkips",
        },
        "lens": {
            "lens": "preferences.lens", "dealSizeProfile": "preferences.dealSizeProfile",
            "mode": "preferences.mode", "priceInEmail": "preferences.priceInEmail",
        },
        "force": ("seen", "deepDone", "deepSkips"),
        "legacy_profile": "cold-email-profile.json",
        "legacy_lens": "cold-email-scorecard.prefs.json",
    },

    # sales-setup: the onboarding skill. Writes the FULL field set so every downstream
    # skill (cold-email, company-research, pitch) wakes up populated.
    # Widest map on purpose — this is the skill that BUILDS the brain.
    "sales-setup": {
        "profile": {
            "name": "business.name",
            "product": "business.product",
            "audience": "business.audience",
            "problem": "business.problem",
            "benefit": "business.benefit",
            "differentiator": "business.differentiator",
            "proof": "business.proof",
            "ask": "business.ask",
            "website": "business.website",
            "wedge": "wedge",
            "register": "voice.register",
            "profileRef": "voice.profileRef",
            "site": "connectedSources.site",
            "sentMailVoice": "connectedSources.sentMailVoice",
            "callNotes": "connectedSources.callNotes",
            "apollo": "connectedSources.apollo",
            "gmail": "connectedSources.gmail",
            "outlook": "connectedSources.outlook",
            # Tier-B working context (background capture writes here, NOT to business.*).
            # Separate paths + force-source="skill" => can never clobber confirmed identity.
            "wcCampaigns": "workingContext.campaigns",
            "wcTargets": "workingContext.targets",
            "wcObjections": "workingContext.objections",
            "wcWins": "workingContext.wins",
            "wcNotes": "workingContext.notes",
            "seen": "capture.seen",
            "deepDone": "capture.deepDone",
            "deepSkips": "capture.deepSkips",
        },
        "lens": {
            "lens": "preferences.lens",
            "dealSizeProfile": "preferences.dealSizeProfile",
            "mode": "preferences.mode",
            "priceInEmail": "preferences.priceInEmail",
        },
        "force": ("seen", "deepDone", "deepSkips",
                  "site", "sentMailVoice", "callNotes", "apollo", "gmail", "outlook",
                  "wcCampaigns", "wcTargets", "wcObjections", "wcWins", "wcNotes"),
        "legacy_profile": None,
        "legacy_lens": None,
    },

    # company-research: the key company-researcher calls (`--skill company-research`). The name
    # predates the skill rename and is kept so no user's saved profile is orphaned. Read-mostly:
    # the research skill consumes identity and
    # write only progress flags + working-context notes — never identity (that's setup's job).
    "company-research": {
        "profile": {
            "name": "business.name", "product": "business.product", "audience": "business.audience",
            "problem": "business.problem", "proof": "business.proof", "website": "business.website",
            "wcTargets": "workingContext.targets", "wcNotes": "workingContext.notes",
            "seen": "capture.seen", "deepDone": "capture.deepDone", "deepSkips": "capture.deepSkips",
        },
        "lens": {"lens": "preferences.lens"},
        "force": ("seen", "deepDone", "deepSkips", "wcTargets", "wcNotes"),
        "legacy_profile": None,
        "legacy_lens": None,
    },
}
