# Content Funnel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire the existing CRM (Django) and static site (`bigbeachal.com`, Porkbun FTP) into the two-track lead funnel defined in [`2026-04-24-content-funnel-design.md`](2026-04-24-content-funnel-design.md). After this plan ships, every lead capture form on bigbeachal.com routes into the right CRM segment, the right agent, and the right drip campaign.

**Architecture:** Backend changes are minimal — most of the campaigns/tracking infrastructure already exists in `apps/campaigns/` and `apps/email_tracker/`. Work is: (1) make `round_robin_assign` track-aware, (2) detect track in the lead-capture view from form metadata, (3) update/create campaign-setup management commands, (4) build a bio splitter static page, (5) wire `campaign_id` into the existing static forms, (6) deploy the (already-built) subdivision page.

**Tech Stack:** Django 4.x, Python 3.x, Django ORM, Django management commands, vanilla HTML/CSS/JS for static pages, Porkbun FTP for static hosting.

**Sequencing notes:**
- Tasks 1–5 are Django (can be done in parallel by different sessions; merge in order)
- Tasks 6–9 are static-site work (sequential because they share FTP)
- Task 10 is a manual user action (Kelly updates her IG bio); listed for completeness

**Source-of-truth links:**
- Design doc: [`docs/plans/2026-04-24-content-funnel-design.md`](2026-04-24-content-funnel-design.md)
- Pages inventory: see `bigbeachal.com active webpages inventory` memory file
- Existing relocation campaign source: `apps/campaigns/management/commands/setup_relocation_campaign.py` (untracked)
- Existing relocation guide site: `relocation-guide/` (untracked)
- Existing subdivision page source: `normal buyers/` (untracked, deploy script `deploy_neighborhoods.cjs` already present)

---

## Task 1: Make `round_robin_assign` track-aware

**Why:** Track 1 leads (relocation) should only be assigned to Dave + Kelly. Track 2 leads (vacation/condo) should only be assigned to Kelly + Kerri. Current implementation assigns to *any* active user in the team.

**Files:**
- Modify: `apps/api/lead_routing.py`
- Modify: `bigbeachal/settings.py` (add `TRACK_AGENTS` config)
- Test: `apps/api/tests/test_lead_routing.py` (new file)

**Step 1: Add settings config**

Edit `bigbeachal/settings.py` (or wherever the project settings live; verify the actual filename with `Glob bigbeachal/settings*.py`). Add near the bottom:

```python
# Track-aware agent assignment for two-funnel lead routing.
# Maps track name to a list of usernames. Lookup is case-sensitive.
TRACK_AGENTS = {
    'track1': ['dave', 'kelly'],     # Relocation funnel
    'track2': ['kelly', 'kerri'],    # Vacation/condo funnel
}
```

**Step 2: Write the failing tests**

Create `apps/api/tests/test_lead_routing.py`:

```python
from django.test import TestCase, override_settings

from apps.accounts.models import Team, User
from apps.api.lead_routing import round_robin_assign


class RoundRobinAssignTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.dave = User.objects.create_user(username="dave", password="x", team=self.team)
        self.kelly = User.objects.create_user(username="kelly", password="x", team=self.team)
        self.kerri = User.objects.create_user(username="kerri", password="x", team=self.team)
        self.outsider = User.objects.create_user(username="someone_else", password="x", team=self.team)

    @override_settings(TRACK_AGENTS={'track1': ['dave', 'kelly'], 'track2': ['kelly', 'kerri']})
    def test_track1_only_assigns_dave_or_kelly(self):
        for _ in range(20):
            assigned = round_robin_assign(self.team, track='track1')
            self.assertIn(assigned.username, ['dave', 'kelly'])

    @override_settings(TRACK_AGENTS={'track1': ['dave', 'kelly'], 'track2': ['kelly', 'kerri']})
    def test_track2_only_assigns_kelly_or_kerri(self):
        for _ in range(20):
            assigned = round_robin_assign(self.team, track='track2')
            self.assertIn(assigned.username, ['kelly', 'kerri'])

    def test_no_track_falls_back_to_existing_round_robin(self):
        # Without a track, any active team member is eligible
        assigned = round_robin_assign(self.team)
        self.assertIn(assigned.username, ['dave', 'kelly', 'kerri', 'someone_else'])

    @override_settings(TRACK_AGENTS={'track1': ['nobody']})
    def test_track_with_no_matching_users_returns_none(self):
        assigned = round_robin_assign(self.team, track='track1')
        self.assertIsNone(assigned)
```

**Step 3: Run tests to verify they fail**

Run: `python manage.py test apps.api.tests.test_lead_routing -v 2`
Expected: FAIL — `round_robin_assign() got an unexpected keyword argument 'track'`

**Step 4: Implement the minimal code**

Replace `apps/api/lead_routing.py` with:

```python
from django.conf import settings
from django.db.models import Count

from apps.accounts.models import User


def round_robin_assign(team, track=None):
    """Assign to the active agent in `team` with the fewest contacts.

    If `track` is provided, restrict the candidate pool to usernames listed
    in settings.TRACK_AGENTS[track]. Returns None if no eligible agents exist.
    """
    agents = User.objects.filter(team=team, is_active=True)
    if track:
        track_usernames = getattr(settings, 'TRACK_AGENTS', {}).get(track, [])
        agents = agents.filter(username__in=track_usernames)
    if not agents.exists():
        return None
    return agents.annotate(
        contact_count=Count('contacts')
    ).order_by('contact_count').first()
```

**Step 5: Run tests to verify they pass**

Run: `python manage.py test apps.api.tests.test_lead_routing -v 2`
Expected: PASS — 4 tests OK

**Step 6: Run full api test suite to confirm no regressions**

Run: `python manage.py test apps.api -v 2`
Expected: All existing tests still PASS (the existing `test_round_robin_assignment` in `test_lead_capture.py` still passes because no `track` argument is passed by the existing view code yet — that wires up in Task 2).

**Step 7: Commit**

```bash
git add apps/api/lead_routing.py apps/api/tests/test_lead_routing.py bigbeachal/settings.py
git commit -m "feat(api): make round_robin_assign track-aware via TRACK_AGENTS setting"
```

---

## Task 2: Detect track in `capture_lead` view and pass to assignment

**Why:** The view currently calls `round_robin_assign(team)` with no track context. We need to derive the track from the form's `source` field or `utm_campaign`, then pass it through.

**Files:**
- Modify: `apps/api/views.py:96-105` (the Contact creation block)
- Modify: `apps/api/tests/test_lead_capture.py` (add new tests)

**Step 1: Write the failing tests**

Append to `apps/api/tests/test_lead_capture.py` (after the existing `test_auto_enroll_campaign`):

```python
    def test_subdivision_form_assigns_track1_agent(self):
        """A lead from source='subdivision_form' must go to a Track 1 agent."""
        from django.test import override_settings
        with override_settings(TRACK_AGENTS={'track1': ['agent1'], 'track2': ['agent2']}):
            response = self.client.post(
                '/api/leads/',
                json.dumps({
                    'first_name': 'Relo',
                    'email': 'relo@test.com',
                    'source': 'subdivision_form',
                }),
                content_type='application/json',
                HTTP_X_API_KEY=self.api_key.key,
            )
            self.assertEqual(response.status_code, 201)
            contact = Contact.objects.get(email='relo@test.com')
            self.assertEqual(contact.assigned_to.username, 'agent1')

    def test_quiz_form_assigns_track2_agent(self):
        """A lead from source='condo_quiz' must go to a Track 2 agent."""
        from django.test import override_settings
        with override_settings(TRACK_AGENTS={'track1': ['agent1'], 'track2': ['agent2']}):
            response = self.client.post(
                '/api/leads/',
                json.dumps({
                    'first_name': 'Vaca',
                    'email': 'vaca@test.com',
                    'source': 'condo_quiz',
                }),
                content_type='application/json',
                HTTP_X_API_KEY=self.api_key.key,
            )
            self.assertEqual(response.status_code, 201)
            contact = Contact.objects.get(email='vaca@test.com')
            self.assertEqual(contact.assigned_to.username, 'agent2')

    def test_utm_campaign_track1_overrides_source(self):
        """utm_campaign=track1-relocation should route to Track 1 even with generic source."""
        from django.test import override_settings
        with override_settings(TRACK_AGENTS={'track1': ['agent1'], 'track2': ['agent2']}):
            response = self.client.post(
                '/api/leads/',
                json.dumps({
                    'first_name': 'Utm',
                    'email': 'utm@test.com',
                    'source': 'landing_page',
                    'utm_campaign': 'track1-relocation',
                }),
                content_type='application/json',
                HTTP_X_API_KEY=self.api_key.key,
            )
            contact = Contact.objects.get(email='utm@test.com')
            self.assertEqual(contact.assigned_to.username, 'agent1')
```

**Step 2: Run tests to verify they fail**

Run: `python manage.py test apps.api.tests.test_lead_capture -v 2`
Expected: 3 new tests FAIL — assignments don't honor track yet.

**Step 3: Implement the track-detection logic in the view**

Edit `apps/api/views.py`. Insert this block between line 67 (after the `source_detail` build) and line 68 (the `# --- Feature 3` block):

```python
    # Detect track for agent assignment.
    # Source field takes priority; falls back to utm_campaign tag.
    source = data.get('source', 'landing_page')
    track = None
    if source == 'subdivision_form' or 'track1' in utm_campaign:
        track = 'track1'
    elif source == 'condo_quiz' or 'track2' in utm_campaign:
        track = 'track2'
```

Then change the `Contact.objects.create(...)` call (currently line 96-105) so the `assigned_to` line becomes:

```python
            assigned_to=round_robin_assign(team, track=track),
```

(Just add `track=track` to the existing call.)

**Step 4: Run tests to verify they pass**

Run: `python manage.py test apps.api.tests.test_lead_capture -v 2`
Expected: All tests PASS, including the 3 new ones.

**Step 5: Commit**

```bash
git add apps/api/views.py apps/api/tests/test_lead_capture.py
git commit -m "feat(api): route lead-capture to track-aware agent pool via source/utm_campaign"
```

---

## Task 3: Add new source choices to Contact.SOURCE_CHOICES

**Why:** The current SOURCE_CHOICES list (`apps/contacts/models.py:33-40`) doesn't include the new track-specific sources. Adding them makes filtering and reporting clean.

**Files:**
- Modify: `apps/contacts/models.py:33-40`
- Migration: auto-generated via `python manage.py makemigrations contacts`

**Step 1: Update SOURCE_CHOICES**

Edit `apps/contacts/models.py:33-40`:

```python
class Contact(models.Model):
    SOURCE_CHOICES = [
        ('landing_page', 'Landing Page'),
        ('manual', 'Manual Entry'),
        ('referral', 'Referral'),
        ('zillow', 'Zillow'),
        ('realtor', 'Realtor.com'),
        ('subdivision_form', 'Subdivision Page (Track 1)'),
        ('condo_quiz', 'Condo Quiz (Track 2)'),
        ('lead_magnet_relocation', 'Lead Magnet — Relocation Guide'),
        ('lead_magnet_condo', 'Lead Magnet — Condo Cheat Sheet'),
        ('bio_splitter', 'IG Bio Splitter Page'),
        ('other', 'Other'),
    ]
```

**Step 2: Generate migration**

Run: `python manage.py makemigrations contacts`
Expected: `Migrations for 'contacts': apps/contacts/migrations/NNNN_alter_contact_source.py - Alter field source on contact`

**Step 3: Apply migration locally to verify it runs**

Run: `python manage.py migrate contacts`
Expected: `Applying contacts.NNNN_alter_contact_source... OK`

**Step 4: Run all contacts tests to confirm no regressions**

Run: `python manage.py test apps.contacts -v 2`
Expected: All PASS.

**Step 5: Commit**

```bash
git add apps/contacts/models.py apps/contacts/migrations/
git commit -m "feat(contacts): add track-specific source choices for new funnel"
```

---

## Task 4: Update the relocation campaign command to the 12-week design

**Why:** `apps/campaigns/management/commands/setup_relocation_campaign.py` (currently untracked) has 5 emails over 21 days. The design calls for 12 emails over 12 weeks. Reuse the existing email bodies for weeks 0, 4, 7, 9, 12 (they map cleanly); leave the other 7 weeks as TODO for Kelly + Dave to write.

**Files:**
- Modify: `apps/campaigns/management/commands/setup_relocation_campaign.py`

**Step 1: Replace the file with the 12-week version**

Rewrite `apps/campaigns/management/commands/setup_relocation_campaign.py`. The structure is the same Django command pattern; just expand the `steps` list. Use 7-day delays (weekly cadence) and reuse the existing 5 email bodies in their new positions:

```python
from django.core.management.base import BaseCommand

from apps.accounts.models import Team
from apps.campaigns.models import Campaign, CampaignStep


WELCOME_BODY = """<p>Hi {{first_name}},</p>
<p>Thanks for requesting our 2026 Gulf Shores Relocation Guide! Moving to the coast is an exciting transition, but it comes with a lot of unique questions—from school zones to 'Gold Fortified' insurance.</p>
<p><strong><a href="/relocation-guide/relocation-guide-pdf.html">Click here to download your guide</a></strong></p>
<p>I've lived and worked here for years, and I'd love to know: what's the #1 thing driving your move?</p>
<p>— {{agent_name}}</p>"""

NEIGHBORHOODS_BODY = """<p>Hey {{first_name}},</p>
<p>Choosing a neighborhood from out of state is the hardest part of relocating.</p>
<p>If you're looking for <strong>Aventura</strong>, you're getting brand-new construction and a massive family presence right near the schools.</p>
<p>If you're looking for <strong>The Peninsula</strong>, you're looking for a gated, quiet, golf-course lifestyle with private beach access.</p>
<p>I actually recorded a few walk-through videos of different areas recently. If you tell me what kind of 'vibe' you're looking for, I can send over the ones that fit you best.</p>
<p>— {{agent_name}}</p>"""

TAXES_INSURANCE_BODY = """<p>Hi {{first_name}},</p>
<p>One of the biggest 'shocks' people have when moving to Gulf Shores is the property tax bill.</p>
<p>In Alabama, we have some of the lowest property taxes in the country. A $500,000 home here typically has a tax bill of around $1,800/year. Compare that to nearly $9,000 in places like Houston or Chicago!</p>
<p><strong>One thing to watch out for:</strong> Insurance. Buying a home with a 'Gold Fortified' certificate can save you 40% on your wind/hail premiums.</p>
<p>I've included a quick breakdown of these financial 'gotchas' on page 3 of the guide I sent you.</p>
<p>— {{agent_name}}</p>"""

SCHOOLS_BODY = """<p>Hey {{first_name}},</p>
<p>One thing I wanted to highlight that isn't always obvious on Zillow is the new Gulf Shores High School project.</p>
<p>Since our school system went independent, we've seen a massive surge in out-of-town families moving to neighborhoods like <strong>Aventura</strong> and <strong>Stonegate</strong> just to be in this district.</p>
<p>If you're moving with students, you definitely want to look at the 'Academy' programs on page 3 of the guide.</p>
<p>Do you have any specific questions about the local schools? I'm happy to help.</p>
<p>— {{agent_name}}</p>"""

TIMELINE_BODY = """<p>Hi {{first_name}},</p>
<p>Most people I help move to Gulf Shores start their search about 12 months before they actually arrive.</p>
<p>Moving across state lines is expensive and stressful, so it pays to have an advocate on the ground before you even list your current house.</p>
<p>I have a few openings this week for a <strong>15-minute 'Relocation Strategy' call</strong>. No sales pitch—just a quick chat to map out your timeline and identify which neighborhoods actually fit your budget.</p>
<p>Reply to this email if you want to grab a time to chat!</p>
<p>— {{agent_name}}</p>"""

# TODO bodies for weeks 1, 2, 3, 5, 6, 8, 10, 11 — Kelly + Dave to write per design doc
TODO_BODY = "<p>TODO: Kelly + Dave to write — see Section 6 of content-funnel-design.md for topic.</p>"


class Command(BaseCommand):
    help = 'Creates the Track 1 — Relocation Welcome (12-week) email campaign'

    def handle(self, *args, **options):
        team = Team.objects.first()
        if not team:
            self.stdout.write(self.style.ERROR('No team found in database.'))
            return

        campaign, created = Campaign.objects.get_or_create(
            name="Track 1 — Relocation Welcome",
            team=team,
            defaults={
                'description': "12-week welcome sequence for relocation buyers (out-of-state movers, retirees, remote workers)."
            }
        )

        if not created:
            self.stdout.write(self.style.WARNING('Campaign already exists. Replacing steps...'))
            campaign.steps.all().delete()

        steps = [
            (0,  "🏖️ Welcome to Gulf Shores! (Your Relocation Guide inside)", WELCOME_BODY),
            (1,  "What everyone gets wrong about Gulf Shores", TODO_BODY),
            (2,  "Cost of living: real numbers vs the brochure", TODO_BODY),
            (3,  "The hurricane question — honest answer", TODO_BODY),
            (4,  "Neighborhood Vibe Check: Aventura vs. The Peninsula", NEIGHBORHOODS_BODY),
            (5,  "I moved here from [your state] — a real story", TODO_BODY),
            (6,  "Year-round vs seasonal life in Gulf Shores", TODO_BODY),
            (7,  "Why your neighbor in your home state is paying 4x your property tax...", TAXES_INSURANCE_BODY),
            (8,  "Here's what a typical week of inventory looks like", TODO_BODY),
            (9,  "Healthcare, schools, and the new GSHS project", SCHOOLS_BODY),
            (10, "How out-of-state buyers actually pull this off", TODO_BODY),
            (11, "Monthly market update — what's moving in Gulf Shores", TODO_BODY),
            (12, "Let's map out your 12-month timeline?", TIMELINE_BODY),
        ]

        for week, subject, body in steps:
            CampaignStep.objects.create(
                campaign=campaign,
                order=week + 1,           # CampaignStep.order is 1-indexed
                delay_days=week * 7,      # weekly cadence
                delay_hours=0,
                subject=subject,
                body=body,
            )

        self.stdout.write(self.style.SUCCESS(
            f'Campaign "{campaign.name}" set up with {len(steps)} steps. ID: {campaign.id}'
        ))
```

**Step 2: Run the command in a fresh shell to verify it works**

Run: `python manage.py setup_relocation_campaign`
Expected: `Campaign "Track 1 — Relocation Welcome" set up with 13 steps. ID: <n>` (or "Campaign already exists. Replacing steps..." if you've run it before).

**Step 3: Verify in Django shell**

Run:
```
python manage.py shell -c "from apps.campaigns.models import Campaign; c = Campaign.objects.get(name='Track 1 — Relocation Welcome'); print([(s.order, s.delay_days, s.subject) for s in c.steps.all()])"
```

Expected: 13 steps printed, with `delay_days` of 0, 7, 14, 21, 28, 35, 42, 49, 56, 63, 70, 77, 84.

**Step 4: Commit**

```bash
git add apps/campaigns/management/commands/setup_relocation_campaign.py
git commit -m "feat(campaigns): expand Track 1 relocation welcome to 12-week cadence"
```

---

## Task 5: Create the Track 2 vacation/condo campaign command

**Why:** Track 2 (vacation/condo) has no existing campaign command. Greenfield 8-week welcome per the design doc.

**Files:**
- Create: `apps/campaigns/management/commands/setup_vacation_campaign.py`

**Step 1: Create the command file**

Create `apps/campaigns/management/commands/setup_vacation_campaign.py`:

```python
from django.core.management.base import BaseCommand

from apps.accounts.models import Team
from apps.campaigns.models import Campaign, CampaignStep


# TODO bodies — Kelly + Kerri to write per Section 6 of content-funnel-design.md
TODO_BODY = "<p>TODO: Kelly + Kerri to write — see Section 6 of content-funnel-design.md for topic.</p>"


class Command(BaseCommand):
    help = 'Creates the Track 2 — Vacation/Condo Welcome (8-week) email campaign'

    def handle(self, *args, **options):
        team = Team.objects.first()
        if not team:
            self.stdout.write(self.style.ERROR('No team found in database.'))
            return

        campaign, created = Campaign.objects.get_or_create(
            name="Track 2 — Vacation/Condo Welcome",
            team=team,
            defaults={
                'description': "8-week welcome sequence for vacation home / condo buyers."
            }
        )

        if not created:
            self.stdout.write(self.style.WARNING('Campaign already exists. Replacing steps...'))
            campaign.steps.all().delete()

        steps = [
            (0, "🏖️ Welcome — your Beach Condo Cheat Sheet & Quiz Results", TODO_BODY),
            (1, "How to read a condo listing — the 3 numbers that matter", TODO_BODY),
            (2, "Building deep-dive: your top match", TODO_BODY),
            (3, "Rental income reality check — real numbers, not listing fantasy", TODO_BODY),
            (4, "Special assessments — the buyer story nobody tells", TODO_BODY),
            (5, "Side-by-side: your top 2 matched buildings", TODO_BODY),
            (6, "How out-of-state buyers handle this remotely", TODO_BODY),
            (7, "Insurance breakdown — wind, flood, contents", TODO_BODY),
            (8, "Want a virtual tour of your top match?", TODO_BODY),
        ]

        for week, subject, body in steps:
            CampaignStep.objects.create(
                campaign=campaign,
                order=week + 1,
                delay_days=week * 7,
                delay_hours=0,
                subject=subject,
                body=body,
            )

        self.stdout.write(self.style.SUCCESS(
            f'Campaign "{campaign.name}" set up with {len(steps)} steps. ID: {campaign.id}'
        ))
```

**Step 2: Run the command**

Run: `python manage.py setup_vacation_campaign`
Expected: `Campaign "Track 2 — Vacation/Condo Welcome" set up with 9 steps. ID: <n>`

**Step 3: Verify**

Run:
```
python manage.py shell -c "from apps.campaigns.models import Campaign; c = Campaign.objects.get(name='Track 2 — Vacation/Condo Welcome'); print([(s.order, s.delay_days, s.subject) for s in c.steps.all()])"
```

Expected: 9 steps with `delay_days` 0, 7, 14, 21, 28, 35, 42, 49, 56.

**Step 4: Commit**

```bash
git add apps/campaigns/management/commands/setup_vacation_campaign.py
git commit -m "feat(campaigns): add Track 2 vacation/condo 8-week welcome scaffold"
```

---

## Task 6: Build the bio splitter page at `bigbeachal.com/start/`

**Why:** Kelly's IG bio currently links straight to `/quiz/`, routing 100% of her audience into the condo funnel. The splitter asks one question and routes to the matching capture endpoint.

**Files:**
- Create: `C:\Users\daved\Desktop\Guide\start\index.html`
- Create: `C:\Users\daved\Desktop\Guide\start\style.css` (optional — can inline)

**Step 1: Verify the parent directory**

Run: `ls "C:/Users/daved/Desktop/Guide/"`
Expected: directory exists; sibling pages like `pages/`, `index-live-from-server.html` are present.

**Step 2: Create the splitter page**

Create `C:\Users\daved\Desktop\Guide\start\index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Welcome to Big Beach AL — what brought you here?</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main>
    <header>
      <img src="https://bigbeachal.com/assets/kelly.jpg" alt="Kelly Davis" class="avatar">
      <h1>What brought you here?</h1>
      <p class="sub">Pick the path that fits — we'll show you what you need.</p>
    </header>

    <nav class="choices">
      <a class="choice relocate" href="https://bigbeachal.com/subdivisions/?utm_source=instagram&utm_medium=bio-link&utm_campaign=track1-relocation&utm_content=bio-splitter">
        <span class="emoji">🏠</span>
        <h2>I'm thinking about moving to Gulf Shores</h2>
        <p>See every neighborhood, school zone, and what year-round life is actually like.</p>
      </a>

      <a class="choice condo" href="https://bigbeachal.com/quiz/?utm_source=instagram&utm_medium=bio-link&utm_campaign=track2-vacation&utm_content=bio-splitter">
        <span class="emoji">🏖️</span>
        <h2>I'm looking for a vacation condo or investment property</h2>
        <p>Take the 60-second quiz — we'll match you to buildings that fit.</p>
      </a>

      <a class="choice guide" href="https://bigbeachal.com/relocation-guide/?utm_source=instagram&utm_medium=bio-link&utm_campaign=track1-relocation&utm_content=bio-splitter-guide">
        <span class="emoji">📖</span>
        <h2>Just curious — send me your free guide</h2>
        <p>The 2026 Gulf Shores Relocation Guide. Email-only, no obligation.</p>
      </a>

      <a class="choice talk" href="https://crm.bigbeachal.com/scheduling/?utm_source=instagram&utm_medium=bio-link&utm_campaign=bio-splitter&utm_content=talk-now">
        <span class="emoji">📞</span>
        <h2>I'm ready to talk to an agent</h2>
        <p>Grab 15 minutes on Kelly's calendar.</p>
      </a>
    </nav>

    <footer>
      <p>Big Beach AL — Kelly Davis, Dave Davis, Kerri Nicketta · Gulf Shores &amp; Orange Beach</p>
    </footer>
  </main>
</body>
</html>
```

Create `C:\Users\daved\Desktop\Guide\start\style.css`:

```css
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: linear-gradient(180deg, #fef9ee 0%, #e8f4f8 100%);
  color: #1f2937;
  min-height: 100vh;
  padding: 2rem 1rem;
}
main { max-width: 540px; margin: 0 auto; }
header { text-align: center; margin-bottom: 2rem; }
.avatar {
  width: 96px; height: 96px; border-radius: 50%;
  object-fit: cover; border: 3px solid #fff; box-shadow: 0 2px 12px rgba(0,0,0,.08);
}
h1 { font-size: 1.75rem; margin-top: 1rem; color: #0d4d6b; font-family: "Playfair Display", Georgia, serif; }
.sub { color: #6b7280; margin-top: .5rem; }
.choices { display: flex; flex-direction: column; gap: 1rem; }
.choice {
  display: block;
  background: #fff;
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
  text-decoration: none;
  color: inherit;
  border: 1px solid #e5e7eb;
  transition: transform .15s ease, box-shadow .15s ease;
}
.choice:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,.10); }
.emoji { font-size: 1.5rem; display: block; margin-bottom: .5rem; }
.choice h2 { font-size: 1.1rem; color: #0d4d6b; }
.choice p { color: #4b5563; margin-top: .25rem; font-size: .95rem; }
footer { text-align: center; color: #9ca3af; font-size: .85rem; margin-top: 2rem; }
```

**Step 3: Smoke-test locally**

Open the file in a browser: `file:///C:/Users/daved/Desktop/Guide/start/index.html`
Expected: 4 cards, mobile-friendly, links work (will 404 for `/subdivisions/` until Task 8 ships — that's fine).

**Step 4: FTP-upload to Porkbun**

Per the existing FTP convention (see memory `reference_porkbun_ftp.md`):
- Upload `index.html` and `style.css` to `/start/` on Porkbun
- Verify by visiting `https://bigbeachal.com/start/`

**Step 5: Commit**

(Note: the static site source under `C:\Users\daved\Desktop\Guide\` is a separate folder from this Django repo and may or may not be its own git repo. If it is, commit there. If not, this step is a no-op for git in this repo.)

```bash
# Inside C:\Users\daved\Desktop\Guide\ if it's a git repo:
# git add start/ && git commit -m "feat(start): add IG bio splitter page"
```

---

## Task 7: Wire `campaign_id` and proper `source` into the existing static forms

**Why:** The lead-capture API already supports `campaign_id` for auto-enrollment (`apps/api/views.py:149-173`). The static forms just need to send it. We also need to set the right `source` value so Task 2's track detection fires.

**Files (all in static site, paths verified via Glob):**
- `C:\Users\daved\Desktop\Guide\` (subdivision form — find the actual form HTML)
- The condo quiz form (lives in the `gsob-condo-search` repo per the pages-inventory memory)
- `relocation-guide/` form (the email capture inside `relocation-guide/api_connection.js`)

**Step 1: Find the actual form locations**

Run:
```
Grep '/api/leads/' C:\Users\daved\Desktop\Guide\ --output_mode files_with_matches
Grep 'capture_lead\|/api/leads/' "c:\Users\daved\AntiGravity Projects\follow up boss\gsob-condo-search\" --output_mode files_with_matches
Grep '/api/leads/' "c:\Users\daved\AntiGravity Projects\follow up boss\relocation-guide\" --output_mode files_with_matches
Grep '/api/leads/' "c:\Users\daved\AntiGravity Projects\follow up boss\normal buyers\" --output_mode files_with_matches
```

Expected: a small handful of files that POST to `/api/leads/`. Note each one for the next step.

**Step 2: Look up the campaign IDs**

Run:
```
python manage.py shell -c "from apps.campaigns.models import Campaign; print([(c.id, c.name) for c in Campaign.objects.filter(name__startswith='Track')])"
```

Expected: two rows like `[(7, 'Track 1 — Relocation Welcome'), (8, 'Track 2 — Vacation/Condo Welcome')]`. Note the IDs.

**Step 3: Update each form's POST body**

For each form found in Step 1, update the JavaScript that POSTs to `/api/leads/` to include the right metadata. Pattern:

**Subdivision form (`normal buyers/` neighborhoods page):**
```javascript
body: JSON.stringify({
  first_name: ...,
  email: ...,
  source: 'subdivision_form',
  campaign_id: <Track 1 campaign id from Step 2>,
  utm_source: 'website',
  utm_campaign: 'track1-relocation',
  utm_content: 'subdivision-form',
  // ... existing fields preserved
})
```

**Condo quiz form (`gsob-condo-search/quiz.js` and the deployed copies):**
```javascript
body: JSON.stringify({
  first_name: ...,
  email: ...,
  source: 'condo_quiz',
  campaign_id: <Track 2 campaign id from Step 2>,
  utm_source: 'website',
  utm_campaign: 'track2-vacation',
  utm_content: 'condo-quiz',
  // ... existing fields preserved
})
```

**Relocation guide capture (`relocation-guide/api_connection.js`):**
```javascript
body: JSON.stringify({
  first_name: ...,
  email: ...,
  source: 'lead_magnet_relocation',
  campaign_id: <Track 1 campaign id>,
  utm_source: 'website',
  utm_campaign: 'track1-relocation',
  utm_content: 'relocation-guide-pdf',
})
```

**Step 4: Test locally with curl**

For each form, test the endpoint directly:

```
curl -X POST https://crm.bigbeachal.com/api/leads/ \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: <key>" \
  -d '{"first_name":"Smoke","email":"smoke-track1@test.com","source":"subdivision_form","campaign_id":<TRACK1_ID>}'
```

Expected: `{"status":"created", "contact_id":N, "assigned_to":"dave"}` (or kelly).

Then check enrollment:
```
python manage.py shell -c "from apps.contacts.models import Contact; c = Contact.objects.get(email='smoke-track1@test.com'); print(c.source, c.assigned_to.username, list(c.enrollments.values_list('campaign__name', flat=True)))"
```

Expected: `subdivision_form dave|kelly ['Track 1 — Relocation Welcome']`

Repeat for Track 2 with `source=condo_quiz`, `campaign_id=<TRACK2_ID>`. Should assign to `kelly|kerri` and enroll in `Track 2 — Vacation/Condo Welcome`.

**Step 5: Deploy via FTP / git push vps**

- Static-site forms (`Guide/`, `relocation-guide/`): FTP-upload changed JS to Porkbun
- `gsob-condo-search/` quiz: per the pages-inventory memory, run `git push vps master` (auto-builds + deploys), then SCP+FTP the rebuilt quiz to Porkbun `/quiz/` per the existing process

**Step 6: Verify in production**

Open each form in a real browser, submit with a unique test email, then check the CRM:
- Contact appears with correct `source`
- Contact appears in the Track 1 or Track 2 campaign enrollment list
- Contact assigned to a Track 1 or Track 2 agent

**Step 7: Commit**

For any files in the Django repo (e.g., `relocation-guide/`, `normal buyers/` — both currently untracked):

```bash
git add relocation-guide/api_connection.js "normal buyers/script.js"
# (adjust paths to whatever the Grep in Step 1 actually found)
git commit -m "feat(static-forms): wire source + campaign_id into all lead-capture forms"
```

For files in the separate `gsob-condo-search/` repo: commit there with `git push vps master`.

---

## Task 8: Deploy the `normal buyers/` neighborhoods page as `bigbeachal.com/subdivisions/`

**Why:** This is the Track 1 capture endpoint our entire design depends on. It's already built (`normal buyers/deploy/index.html`) but not deployed.

**Files:**
- Source: `c:\Users\daved\AntiGravity Projects\follow up buss\normal buyers\deploy\` (typo: actually `follow up boss\normal buyers\deploy\`)
- Deploy target: Porkbun FTP `/subdivisions/`

**Step 1: Read the existing deploy script**

Run: `Read "c:\Users\daved\AntiGravity Projects\follow up boss\normal buyers\deploy_neighborhoods.cjs"`
Expected: an existing Node-based FTP deploy script. Inspect what it deploys to and where.

**Step 2: Decide URL path and update deploy target if needed**

Confirm the target path on Porkbun — design says `bigbeachal.com/subdivisions/`. If `deploy_neighborhoods.cjs` targets a different path (e.g., `/neighborhoods/`), update it to `/subdivisions/`.

**Step 3: Run the deploy script**

Run: `node "normal buyers/deploy_neighborhoods.cjs"`
Expected: Files upload to Porkbun. Log shows each file uploaded.

**Step 4: Smoke-test in browser**

Open `https://bigbeachal.com/subdivisions/`
Expected: page loads, neighborhoods are listed with photos, the form to capture leads is visible.

**Step 5: Test form submission end-to-end**

Submit the form with a unique test email. Verify in CRM that the contact landed with `source=subdivision_form` and was enrolled in Track 1. (This depends on Task 7 already being complete.)

**Step 6: Commit the source files to the Django repo**

```bash
git add "normal buyers/"
git commit -m "feat(subdivisions): add Track 1 subdivision page source + deploy script"
```

---

## Task 9: Verify the relocation-guide site is wired up correctly

**Why:** The `relocation-guide/` directory is untracked but appears built. We need to confirm the email capture form on `index.html` posts to the lead-capture API with the right `source` and `campaign_id`.

**Files:**
- `relocation-guide/index.html`
- `relocation-guide/api_connection.js`

**Step 1: Read both files**

Run:
```
Read "c:\Users\daved\AntiGravity Projects\follow up boss\relocation-guide\index.html"
Read "c:\Users\daved\AntiGravity Projects\follow up boss\relocation-guide\api_connection.js"
```

Expected: identify the form submit handler and the API call.

**Step 2: Confirm or update**

If the API call already includes `source` and `campaign_id` from Task 7's edits, you're done. Otherwise, apply the Task 7 pattern to `api_connection.js`.

**Step 3: Confirm the relocation guide site is uploaded to Porkbun**

Visit `https://bigbeachal.com/relocation-guide/` in a browser.
- If it loads: it's already deployed.
- If 404: FTP-upload `relocation-guide/` contents to Porkbun `/relocation-guide/`.

**Step 4: Smoke-test the capture flow**

Submit the form on the live site with a unique test email. Verify in CRM:
- Contact created with `source=lead_magnet_relocation`
- Contact assigned to a Track 1 agent
- Contact enrolled in Track 1 campaign

**Step 5: Commit relocation-guide source to Django repo**

```bash
git add relocation-guide/
git commit -m "feat(relocation-guide): add Relocation Guide PDF site source"
```

---

## Task 10: Update Kelly's IG bio link (manual)

**Why:** Currently points to `bigbeachal.com/quiz` — routes 100% of Kelly's IG audience to Track 2, losing every relocation lead. Swap to `/start` after Task 6 ships.

**Steps:** (This is a manual user action — not for the engineer.)
1. Kelly opens Instagram on her phone
2. Profile → Edit profile → Website
3. Replace `bigbeachal.com/quiz` with `bigbeachal.com/start`
4. Save

Verification: open Kelly's IG profile in a fresh browser/incognito window, tap the bio link, confirm it loads the splitter page.

---

## Done Criteria

After all tasks ship, the following should be true:

- [ ] A POST to `/api/leads/` with `source=subdivision_form` is assigned to a Track 1 agent (Dave or Kelly) and enrolled in `Track 1 — Relocation Welcome`
- [ ] A POST to `/api/leads/` with `source=condo_quiz` is assigned to a Track 2 agent (Kelly or Kerri) and enrolled in `Track 2 — Vacation/Condo Welcome`
- [ ] `bigbeachal.com/start/` renders the bio splitter page with 4 working choices
- [ ] `bigbeachal.com/subdivisions/` renders the neighborhoods page and its capture form lands as Track 1
- [ ] `bigbeachal.com/relocation-guide/` renders and its capture form lands as Track 1
- [ ] `bigbeachal.com/quiz/` capture form lands as Track 2
- [ ] Kelly's IG bio links to `/start`
- [ ] Both Django campaigns visible in the CRM admin with correct step counts (13 / 9)
- [ ] All Django tests pass: `python manage.py test apps.api apps.contacts apps.campaigns`

After backend tasks (1–5) and form wiring (7) ship, the funnel mechanically works end-to-end, even with the TODO email bodies in the campaigns. Kelly + Dave/Kerri can fill in the real email content as a parallel content-writing track without blocking the engineering.
