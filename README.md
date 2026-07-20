# 🏉 Wallabies 2026 Auto-Updating Calendar

A self-hosted calendar feed for the **Australia Wallabies (Men's 15s)** 2026 Test
season. It publishes one subscribe URL that your phone/computer calendar keeps in
sync automatically.

## Why this exists

The Wallabies' 2026 season is split across two competitions and **no single public
feed covers all of it**:

- **Nations Championship** (6 Tests: Ireland, France, Italy, England, Scotland,
  Wales) — pulled **live** from a structured feed, so kickoff times and results
  update automatically.
- **Rugby Championship / Bledisloe** (Japan, Argentina ×2, South Africa,
  New Zealand ×2) — held as stable data in `baseline.json`, because no public
  structured feed carries these.

The build script merges both into one `.ics` and GitHub publishes it for free.

---

## One-time setup (about 10 minutes)

1. **Create a new GitHub repository.** Any name works, e.g. `wallabies-calendar`.
   Make it **Public** (required for free GitHub Pages).

2. **Add these files** to the repo. Easiest: on the repo's main page click
   **Add file → Upload files**, drag in everything from this folder
   (keep the `.github/` and `docs/` folder structure), and commit.

3. **Turn on GitHub Pages via Actions.** In the repo go to
   **Settings → Pages**, and under **Build and deployment → Source** choose
   **GitHub Actions**. (You don't pick a branch — the workflow handles it.)

4. **Run the workflow once.** Go to the **Actions** tab, click
   **“Build & publish Wallabies calendar”**, then **Run workflow**.
   Wait ~1 minute for the green tick.

5. **Get your subscribe URL.** It will be:

   ```
   https://<your-github-username>.github.io/<repo-name>/wallabies-2026.ics
   ```

   Open that URL once in a browser to confirm it downloads.

---

## Subscribe on your devices

- **Apple Calendar (iPhone/Mac):** replace `https` with `webcal` in the URL and
  open it — e.g. `webcal://<username>.github.io/<repo>/wallabies-2026.ics` — or
  on Mac: **File → New Calendar Subscription** and paste the `https` URL.
- **Google Calendar:** left sidebar → **Other calendars → + → From URL**, paste
  the `https` URL. (Google refreshes external calendars on its own schedule,
  often every 12–24h.)
- **Outlook:** **Add calendar → Subscribe from web**, paste the `https` URL.

Subscribe once and every future rebuild flows through automatically.

---

## How updates happen

- A scheduled GitHub Action rebuilds the feed **daily** (06:00 NZ time) and also
  whenever you edit `baseline.json`. You can trigger it anytime from the
  **Actions** tab (**Run workflow**).
- Each run **auto-discovers** every fixturedownload competition Australia plays in
  for the current and next calendar year, so times and results refresh
  automatically. The rest comes from `baseline.json`.

## Does it keep working after 2026?

Yes — it's built to roll over:

- **No year is hardcoded.** The build reads today's date, then looks up every
  rugby competition Australia is in for the current + next year (Nations
  Championship, The Rugby Championship, Bledisloe, Rugby World Cup, Autumn
  internationals, …). When 2027's fixtures get published, they appear on their
  own.
- **The view auto-rolls.** It shows recent results (~6 months back) through the
  upcoming season (~18 months ahead) and quietly drops older seasons — the
  calendar never fills up with ancient matches.
- **The only manual bit** is the same as before: some Rugby Championship *away*
  kickoff times aren't in any public feed. Once a new season is announced, append
  those Tests to `baseline.json` (see below). Everything a feed already covers is
  automatic. If you skip this, those Tests simply won't appear until a feed
  carries them — nothing breaks.

### Updating a Rugby Championship kickoff time

When an away Test's time is confirmed (Japan Aug 8, Argentina Aug 29 & Sep 5,
NZ Oct 10), edit that entry in **`baseline.json`**:

```json
{
  "id": "rc-japan-away",
  "dateUtc": "2026-08-08 09:00:00Z",   // set the UTC kickoff...
  "allDay": false,                      // ...and flip this to false
  ...
}
```

Commit the change — the calendar rebuilds and everyone's subscription updates.
`dateUtc` is always in **UTC** (calendars convert to each viewer's local time).

---

## Files

| File | Purpose |
|------|---------|
| `build_calendar.py` | Merges live feed + `baseline.json` → `docs/wallabies-2026.ics` (standard library only) |
| `baseline.json` | The Rugby Championship Tests + editable kickoff times |
| `.github/workflows/build-calendar.yml` | Daily scheduled rebuild + Pages deploy |
| `docs/` | Published output (the `.ics` and a small landing page) |

## Notes on reliability

If the live feed is ever unreachable, the build **falls back to `baseline.json`**
so the calendar never breaks or goes empty. Kickoff times marked *TBC* appear as
all-day events until confirmed.
