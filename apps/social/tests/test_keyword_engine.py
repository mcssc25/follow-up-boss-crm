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
            trigger_event='both',
            reply_text='Here is the condo guide!',
        )
        self.trigger_phoenix = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Phoenix',
            match_type='exact',
            platform='instagram',
            trigger_event='message',
            reply_text='Check out Phoenix tours!',
        )
        self.trigger_hello = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Hi there',
            match_type='starts_with',
            platform='facebook',
            trigger_event='message',
            reply_text='Welcome!',
        )
        self.trigger_comment = KeywordTrigger.objects.create(
            team=self.team,
            keyword='guide',
            match_type='contains',
            platform='instagram',
            trigger_event='comment',
            response_type='private_reply',
            reply_text='Sending the guide now.',
        )

    def test_contains_match(self):
        trigger = find_matching_trigger(
            self.team, 'I want Condos please', 'instagram', event_type='message'
        )
        self.assertEqual(trigger, self.trigger_condos)

    def test_contains_case_insensitive(self):
        trigger = find_matching_trigger(
            self.team, 'show me condos', 'instagram', event_type='message'
        )
        self.assertEqual(trigger, self.trigger_condos)

    def test_exact_match(self):
        trigger = find_matching_trigger(
            self.team, 'Phoenix', 'instagram', event_type='message'
        )
        self.assertEqual(trigger, self.trigger_phoenix)

    def test_starts_with_match(self):
        trigger = find_matching_trigger(
            self.team, 'Hi there friend!', 'facebook', event_type='message'
        )
        self.assertEqual(trigger, self.trigger_hello)

    def test_platform_filter_instagram(self):
        trigger = find_matching_trigger(
            self.team, 'Hi there!', 'instagram', event_type='message'
        )
        self.assertIsNone(trigger)

    def test_event_type_filter_for_comment(self):
        trigger = find_matching_trigger(
            self.team, 'Please send the guide', 'instagram', event_type='comment'
        )
        self.assertEqual(trigger, self.trigger_comment)

    def test_longer_exact_match_wins(self):
        more_specific = KeywordTrigger.objects.create(
            team=self.team,
            keyword='condos in phoenix',
            match_type='contains',
            platform='both',
            trigger_event='message',
            reply_text='Specific reply',
        )
        trigger = find_matching_trigger(
            self.team, 'I want condos in phoenix', 'instagram', event_type='message'
        )
        self.assertEqual(trigger, more_specific)

    def test_no_match(self):
        trigger = find_matching_trigger(
            self.team, 'What is the weather?', 'instagram', event_type='message'
        )
        self.assertIsNone(trigger)
