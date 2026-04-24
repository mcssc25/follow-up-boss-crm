from django.core.management.base import BaseCommand, CommandError

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

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Replace existing campaign steps even if the campaign already exists.',
        )

    def handle(self, *args, **options):
        team = Team.objects.first()
        if not team:
            raise CommandError('No team found in database.')

        campaign, created = Campaign.objects.get_or_create(
            name="Track 1 — Relocation Welcome",
            team=team,
            defaults={
                'description': "12-week welcome sequence for relocation buyers (out-of-state movers, retirees, remote workers)."
            }
        )

        if not created:
            if not options['force']:
                raise CommandError(
                    f'Campaign "{campaign.name}" already exists with {campaign.steps.count()} step(s). '
                    f'Pass --force to delete and recreate them. Existing admin edits will be lost.'
                )
            self.stdout.write(self.style.WARNING('--force passed: replacing existing steps...'))
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
