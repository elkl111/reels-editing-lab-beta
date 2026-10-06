---
name: update
description: Update the Reels Editing Lab to the newest version. Use when the user says "update", "update the Lab", "is there a new version?", or was told a new version is out.
---

# Update the Lab

1. Run `python3 tools/update.py --check`.
   - `UPDATE=current`: tell them they're on the newest version. Done.
   - `UPDATE=available`: show the changes in 2–4 plain bullets from the printed changelog. Say their looks, preferences and reels won't be touched, and ask "Update now?"
   - `UPDATE=not-configured` or `download-failed`: explain in one line and stop.
2. When they say yes, run `python3 tools/update.py`. It keeps a backup of the old version in `.lab-backup/`.
3. Afterwards, tell them:
   - "Updated to <version>."
   - one line on the most useful new thing
   - **"Start a new chat in this folder so I pick up the new version."** The skills in this chat are the old ones.
4. If anything fails halfway, the previous engine is in `.lab-backup/<old version>/`. Tell them, and use `/report-problem`.
