---
name: report-problem
description: Bundle a problem report for the Lab's maker. Use when the user says something is broken, wrong or confusing and wants to report it ("report a problem", "this isn't working, tell Elena", "send feedback"), or when a tool keeps failing after you've tried to fix it.
---

# Report a problem

1. If they haven't already said, ask one question: "What went wrong, or what did you expect instead?" Keep their words.
2. Run:
   `uv run tools/report.py projects/<name> --note "<their words, plus one line from you on what you saw>" --error "<the last error text, if any>"`
   Leave out the project if it's not about a reel. The tool uses the latest one.
3. It saves `Reels Lab report <date>.zip` on their Desktop and shows it in Finder. It holds the plan files, a small low-quality preview, the setup check and versions. Never the original footage.
4. Tell them, in two lines:
   - "Report saved on your Desktop" plus the `support` line from `lab.json` (who to send it to)
   - one line on whether you could work around the problem for now
5. Still try to help: if you can fix or work around it in the chat, do.
