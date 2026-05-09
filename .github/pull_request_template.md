<!--
Keep this title concise (<70 chars). Conventional Commits prefix encouraged:
  feat: fix: chore: docs: refactor: test: perf: ci:

📖 First-time contributor? Read CONTRIBUTING.md first:
   https://github.com/dokson/hedge-fund-tracker/blob/master/CONTRIBUTING.md
-->

## Summary

<!-- 1–3 bullets on what changed and why. Focus on the "why". -->

-

## Type of change

<!-- Check all that apply -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (existing behavior would change)
- [ ] Refactor / code quality (no behavior change)
- [ ] Docs only
- [ ] CI / tooling only

## Test plan

<!-- How did you verify this? Reviewers should be able to reproduce. -->

- [ ] `pipenv run python -m unittest discover` — all green
- [ ] `cd app/frontend && npm test` — all green
- [ ] `pipenv run lint && cd app/frontend && npm run lint && npm run type-check` — clean
- [ ] Manual smoke (describe below if UI/UX touched):

## Screenshots / recordings

<!-- For UI changes, drop a screenshot or short clip. Show before AND after if relevant. Skip otherwise. -->

## Footguns / things reviewers should look at

<!-- Anything subtle: SSE behavior, denomination matching, gh-pages mode, etc. Be honest about what you're unsure about. -->

## Linked issues

<!-- Closes #123, Refs #456 -->

---

<details>
<summary>Self-review checklist (click to expand)</summary>

- [ ] Followed TDD (failing test first, then minimal code) — see `AGENTS.md` § TDD
- [ ] No `print()` debug left behind, no commented-out code
- [ ] Docstrings on every new function/method (multi-line, AGENTS.md § Docstrings)
- [ ] No secrets/keys in diff (CI runs `detect-private-key` but double-check)
- [ ] If touching `app/server.py` SSE → reviewed Footguns § "SSE redirects sys.stdout"
- [ ] If touching `hedge_funds.csv` Denomination → spot-checked at least 1 non-quarterly match
- [ ] If touching `app/frontend/src/lib/config.ts` → tested both local and `npm run build:gh-pages`

</details>
