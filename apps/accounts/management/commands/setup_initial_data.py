from django.core.management.base import BaseCommand

from apps.accounts.models import Team, User
from apps.api.models import APIKey
from apps.campaigns.models import Campaign, CampaignStep
from apps.contacts.models import SmartList
from apps.pipeline.models import Pipeline, PipelineStage


class Command(BaseCommand):
    help = 'Set up initial data for a new CRM installation'

    def add_arguments(self, parser):
        parser.add_argument('--team-name', default='My Team')
        parser.add_argument('--admin-username', default='admin')
        parser.add_argument('--admin-email', required=True)
        parser.add_argument('--admin-password', required=True)

    def handle(self, *args, **options):
        # Create team
        team, _ = Team.objects.get_or_create(name=options['team_name'])

        # Create admin user
        if not User.objects.filter(username=options['admin_username']).exists():
            user = User.objects.create_superuser(
                username=options['admin_username'],
                email=options['admin_email'],
                password=options['admin_password'],
                role='admin',
                team=team,
            )
            self.stdout.write(f"Created admin user: {user.username}")

        # Create Buyer Pipeline
        buyer_pipeline, _ = Pipeline.objects.get_or_create(
            name="Buyer Pipeline", team=team,
        )
        buyer_stages = [
            ("New Lead", 1, "#6366f1"),
            ("Contacted", 2, "#8b5cf6"),
            ("Showing", 3, "#a855f7"),
            ("Offer", 4, "#f59e0b"),
            ("Under Contract", 5, "#10b981"),
            ("Closed Won", 6, "#22c55e"),
            ("Closed Lost", 7, "#ef4444"),
        ]
        for name, order, color in buyer_stages:
            PipelineStage.objects.get_or_create(
                pipeline=buyer_pipeline,
                name=name,
                defaults={'order': order, 'color': color},
            )

        # Create Seller Pipeline
        seller_pipeline, _ = Pipeline.objects.get_or_create(
            name="Seller Pipeline", team=team,
        )
        seller_stages = [
            ("New Lead", 1, "#6366f1"),
            ("Listing Appointment", 2, "#8b5cf6"),
            ("Listed", 3, "#a855f7"),
            ("Under Contract", 4, "#10b981"),
            ("Closed", 5, "#22c55e"),
        ]
        for name, order, color in seller_stages:
            PipelineStage.objects.get_or_create(
                pipeline=seller_pipeline,
                name=name,
                defaults={'order': order, 'color': color},
            )

        # Create Smart Lists
        smart_lists = [
            ("New This Week", {"created_days_ago_lt": 7}),
            ("No Contact 30 Days", {"last_contacted_days_ago_gt": 30}),
            ("Landing Page Leads", {"source": "landing_page"}),
            ("Unassigned", {"assigned_to": None}),
        ]
        for name, filters in smart_lists:
            SmartList.objects.get_or_create(
                name=name, team=team, defaults={'filters': filters},
            )

        # Create sample campaign template
        campaign, created = Campaign.objects.get_or_create(
            name="New Buyer Lead Drip",
            team=team,
            defaults={
                'description': 'Automated follow-up sequence for new buyer leads',
                'is_active': False,
                'created_by': User.objects.filter(team=team).first(),
            },
        )
        if created:
            steps = [
                (
                    1, 0, 0,
                    "Welcome! Let's find your dream home",
                    "<p>Hi {{first_name}},</p>"
                    "<p>Thanks for reaching out! I'm {{agent_name}}, and I'd love to "
                    "help you find your perfect home.</p>"
                    "<p>What are you looking for? Let me know your must-haves and I'll "
                    "start putting together some options.</p>"
                    "<p>Best,<br>{{agent_name}}<br>{{agent_phone}}</p>",
                ),
                (
                    2, 3, 0,
                    "Some homes you might love",
                    "<p>Hi {{first_name}},</p>"
                    "<p>I've been thinking about what might work for you. I have a few "
                    "properties I'd love to show you.</p>"
                    "<p>When would be a good time to chat? I'm available most days this "
                    "week.</p>"
                    "<p>{{agent_name}}<br>{{agent_phone}}</p>",
                ),
                (
                    3, 7, 0,
                    "Quick market update for you",
                    "<p>Hi {{first_name}},</p>"
                    "<p>Just wanted to share a quick update on the market. Homes are "
                    "moving fast right now, and I want to make sure you don't miss out "
                    "on the right one.</p>"
                    "<p>Let's schedule a time to go over your options. No pressure "
                    "— just want to make sure you're informed!</p>"
                    "<p>{{agent_name}}</p>",
                ),
                (
                    4, 14, 0,
                    "Still looking? I'm here to help",
                    "<p>Hi {{first_name}},</p>"
                    "<p>I know buying a home is a big decision and there's no rush. "
                    "I just wanted to let you know I'm here whenever you're ready.</p>"
                    "<p>Feel free to reach out anytime — even if it's just to ask a "
                    "question.</p>"
                    "<p>{{agent_name}}<br>{{agent_phone}}<br>{{agent_email}}</p>",
                ),
            ]
            for order, days, hours, subject, body in steps:
                CampaignStep.objects.create(
                    campaign=campaign,
                    order=order,
                    delay_days=days,
                    delay_hours=hours,
                    subject=subject,
                    body=body,
                )

        # Create API key
        APIKey.objects.get_or_create(
            team=team, name="Landing Page", defaults={'is_active': True},
        )

        self.stdout.write(self.style.SUCCESS("Initial data setup complete!"))
