from django.test import TestCase

from apps.accounts.models import Team
from apps.social.engine import find_matching_trigger
from apps.social.models import KeywordTrigger


class KeywordMatchingTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.trigger_condos = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Condos',
            match_type='contains',
            platform='both',
            reply_text='Here is the condo guide!',
        )
        self.trigger_phoenix = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Phoenix',
            match_type='exact',
            platform='instagram',
            reply_text='Check out Phoenix tours!',
        )
        self.trigger_hello = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Hi ',
            match_type='starts_with',
            platform='facebook',
            reply_text='Welcome!',
        )

    def test_contains_match(self):
        trigger = find_matching_trigger(
            self.team, 'I want Condos please', 'instagram'
        )
        self.assertEqual(trigger, self.trigger_condos)

    def test_contains_case_insensitive(self):
        trigger = find_matching_trigger(
            self.team, 'show me condos', 'instagram'
        )
        self.assertEqual(trigger, self.trigger_condos)

    def test_exact_match(self):
        trigger = find_matching_trigger(
            self.team, 'Phoenix', 'instagram'
        )
        self.assertEqual(trigger, self.trigger_phoenix)

    def test_exact_no_partial(self):
        trigger = find_matching_trigger(
            self.team, 'Phoenix condos', 'instagram'
        )
        # "Phoenix" is exact match only, so this should NOT match phoenix
        # but "condos" contains match should fire
        self.assertEqual(trigger, self.trigger_condos)

    def test_starts_with_match(self):
        trigger = find_matching_trigger(
            self.team, 'Hi there!', 'facebook'
        )
        self.assertEqual(trigger, self.trigger_hello)

    def test_platform_filter_instagram(self):
        # "Hi " trigger is facebook-only, should not match on instagram
        trigger = find_matching_trigger(
            self.team, 'Hi there!', 'instagram'
        )
        self.assertIsNone(trigger)

    def test_platform_both_matches_any(self):
        trigger = find_matching_trigger(
            self.team, 'Show me condos', 'facebook'
        )
        self.assertEqual(trigger, self.trigger_condos)

    def test_no_match(self):
        trigger = find_matching_trigger(
            self.team, 'What is the weather?', 'instagram'
        )
        self.assertIsNone(trigger)

    def test_inactive_trigger_skipped(self):
        self.trigger_condos.is_active = False
        self.trigger_condos.save()
        trigger = find_matching_trigger(
            self.team, 'I want condos', 'instagram'
        )
        self.assertIsNone(trigger)
