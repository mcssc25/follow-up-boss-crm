from django.test import TestCase

from apps.accounts.models import Team
from apps.campaigns.models import Campaign
from apps.social.models import KeywordTrigger, MessageLog, SocialAccount


class SocialAccountModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")

    def test_create_social_account(self):
        account = SocialAccount.objects.create(
            team=self.team,
            platform='instagram',
            page_id='12345',
            page_name='Test Page',
            access_token='token123',
        )
        self.assertEqual(str(account), "Test Page (instagram)")
        self.assertTrue(account.is_active)
        self.assertFalse(account.webhook_verified)
        self.assertFalse(account.app_subscribed)
        self.assertEqual(account.last_webhook_error, '')


class KeywordTriggerModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")

    def test_create_keyword_trigger(self):
        trigger = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Condos',
            match_type='contains',
            platform='both',
            trigger_event='comment',
            response_type='private_reply',
            reply_text='Thanks for your interest! Here is the guide.',
        )
        self.assertEqual(str(trigger), "Condos (both)")
        self.assertTrue(trigger.is_active)
        self.assertTrue(trigger.create_contact)
        self.assertEqual(trigger.trigger_event, 'comment')
        self.assertEqual(trigger.response_type, 'private_reply')

    def test_trigger_with_campaign(self):
        campaign = Campaign.objects.create(name="Condo Drip", team=self.team)
        trigger = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Phoenix',
            reply_text='Check out Phoenix condos!',
            campaign=campaign,
        )
        self.assertEqual(trigger.campaign, campaign)


class MessageLogModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.account = SocialAccount.objects.create(
            team=self.team,
            platform='instagram',
            page_id='12345',
            page_name='Test Page',
            access_token='token',
        )

    def test_create_message_log(self):
        log = MessageLog.objects.create(
            social_account=self.account,
            sender_id='ig_user_123',
            sender_name='Jane Smith',
            message_text='I want Condos',
            platform='instagram',
            event_type='comment',
            comment_id='comment_1',
            post_id='post_1',
            raw_payload={'sample': True},
        )
        self.assertFalse(log.reply_sent)
        self.assertIsNone(log.trigger_matched)
        self.assertIsNone(log.contact_created)
        self.assertEqual(log.event_type, 'comment')
        self.assertEqual(log.comment_id, 'comment_1')
