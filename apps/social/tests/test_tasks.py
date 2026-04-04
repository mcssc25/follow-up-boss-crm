from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import Team, User
from apps.campaigns.models import Campaign
from apps.contacts.models import Contact
from apps.social.models import KeywordTrigger, MessageLog, SocialAccount
from apps.social.tasks import process_incoming_message


class ProcessIncomingMessageTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.agent = User.objects.create_user(
            username="kelly", password="pass", team=self.team
        )
        self.account = SocialAccount.objects.create(
            team=self.team,
            platform='instagram',
            page_id='page_123',
            page_name='Kelly Realty',
            access_token='token123',
            instagram_account_id='ig_123',
        )
        self.trigger = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Condos',
            match_type='contains',
            platform='both',
            reply_text='Here is the condo guide!',
            reply_link='https://example.com/guide.pdf',
            tags=['condos', 'interested'],
            create_contact=True,
        )

    @patch('apps.social.tasks.send_message')
    @patch('apps.social.tasks.get_user_profile')
    def test_keyword_match_creates_contact_and_replies(
        self, mock_profile, mock_send
    ):
        mock_profile.return_value = {'name': 'Jane Smith'}
        mock_send.return_value = {'success': True}

        process_incoming_message(
            page_id='page_123',
            platform='instagram',
            sender_id='user_456',
            message_text='I want Condos',
        )

        # Contact created
        contact = Contact.objects.get(
            custom_fields__instagram_id='user_456',
        )
        self.assertEqual(contact.first_name, 'Jane')
        self.assertEqual(contact.last_name, 'Smith')
        self.assertIn('condos', contact.tags)

        # Message logged
        log = MessageLog.objects.get(sender_id='user_456')
        self.assertEqual(log.trigger_matched, self.trigger)
        self.assertTrue(log.reply_sent)
        self.assertEqual(log.contact_created, contact)

        # Reply sent with link appended
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        self.assertIn('condo guide', call_args[1]['text'])
        self.assertIn('https://example.com/guide.pdf', call_args[1]['text'])

    @patch('apps.social.tasks.send_message')
    @patch('apps.social.tasks.get_user_profile')
    def test_no_match_logs_without_reply(self, mock_profile, mock_send):
        mock_profile.return_value = {'name': 'John Doe'}

        process_incoming_message(
            page_id='page_123',
            platform='instagram',
            sender_id='user_789',
            message_text='What is the weather?',
        )

        # Message logged but no trigger
        log = MessageLog.objects.get(sender_id='user_789')
        self.assertIsNone(log.trigger_matched)
        self.assertFalse(log.reply_sent)

        # No reply sent
        mock_send.assert_not_called()

    @patch('apps.social.tasks.send_message')
    @patch('apps.social.tasks.get_user_profile')
    def test_existing_contact_updated_not_duplicated(
        self, mock_profile, mock_send
    ):
        mock_profile.return_value = {'name': 'Jane Smith'}
        mock_send.return_value = {'success': True}

        # Pre-existing contact from same sender
        Contact.objects.create(
            first_name='Jane',
            last_name='Smith',
            team=self.team,
            custom_fields={'instagram_id': 'user_456'},
        )

        process_incoming_message(
            page_id='page_123',
            platform='instagram',
            sender_id='user_456',
            message_text='Show me Condos again',
        )

        # Should not create a duplicate
        self.assertEqual(
            Contact.objects.filter(
                custom_fields__instagram_id='user_456'
            ).count(),
            1,
        )

    @patch('apps.social.tasks.send_message')
    @patch('apps.social.tasks.get_user_profile')
    def test_campaign_enrollment(self, mock_profile, mock_send):
        mock_profile.return_value = {'name': 'Bob Jones'}
        mock_send.return_value = {'success': True}

        campaign = Campaign.objects.create(
            name="Condo Drip", team=self.team
        )
        self.trigger.campaign = campaign
        self.trigger.save()

        process_incoming_message(
            page_id='page_123',
            platform='instagram',
            sender_id='user_enroll',
            message_text='I love Condos!',
        )

        contact = Contact.objects.get(
            custom_fields__instagram_id='user_enroll',
        )
        self.assertTrue(
            campaign.enrollments.filter(contact=contact, is_active=True).exists()
        )
