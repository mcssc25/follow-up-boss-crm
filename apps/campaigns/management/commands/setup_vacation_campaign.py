from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Team
from apps.campaigns.models import Campaign, CampaignStep


# TODO bodies — Kelly + Kerri to write per Section 6 of content-funnel-design.md
TODO_BODY = "<p>TODO: Kelly + Kerri to write — see Section 6 of content-funnel-design.md for topic.</p>"


class Command(BaseCommand):
    help = 'Creates the Track 2 — Vacation/Condo Welcome (8-week) email campaign'

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
            name="Track 2 — Vacation/Condo Welcome",
            team=team,
            defaults={
                'description': "8-week welcome sequence for vacation home / condo buyers."
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
