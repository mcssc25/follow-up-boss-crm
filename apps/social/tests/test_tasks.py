from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import Team, User
from apps.campaigns.models import Campaign
from apps.contacts.models import Contact
from apps.social.models import KeywordTrigger, MessageLog, SocialAccount
from apps.social.tasks import process_incoming_event


class ProcessIncomingEventTest(TestCase):
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
        self.message_trigger = KeywordTrigger.objects.create(
            team=self.team,
            keyword='Condos',
            match_type='contains',
            platform='both',
            trigger_event='message',
            response_type='message',
            reply_text='Here is the condo guide!',
            reply_link='https://example.com/guide.pdf',
            tags=['condos', 'interested'],
            create_contact=True,
        )
        self.comment_trigger = KeywordTrigger.objects.create(
            team=self.team,
            keyword='guide',
            match_type='contains',
            platform='instagram',
            trigger_event='comment',
            response_type='private_reply',
            reply_text='Sending the guide in private.',
            tags=['comment-lead'],
            create_contact=True,
        )

    @patch('apps.social.tasks.send_message')
    @patch('apps.social.tasks.get_user_profile')
    def test_message_trigger_creates_contact_and_replies(
        self, mock_profile, mock_send
    ):
        mock_profile.return_value = {'name': 'Jane Smith'}
        mock_send.return_value = {'success': True}

        process_incoming_event(
            page_id='page_123',
            platform='instagram',
            sender_id='user_456',
            message_text='I want Condos',
            event_type='message',
            external_event_id='mid.1',
        )

        contact = Contact.objects.get(custom_fields__instagram_id='user_456')
        self.assertEqual(contact.first_name, 'Jane')
        self.assertIn('condos', contact.tags)

        log = MessageLog.objects.get(sender_id='user_456')
        self.assertEqual(log.trigger_matched, self.message_trigger)
        self.assertTrue(log.reply_sent)
        self.assertEqual(log.event_type, 'message')

        mock_send.assert_called_once()
        self.assertIn('https://example.com/guide.pdf', mock_send.call_args.kwargs['text'])

    @patch('apps.social.tasks.send_private_reply')
    def test_comment_trigger_uses_private_reply(self, mock_private_reply):
        mock_private_reply.return_value = {'success': True}

        process_incoming_event(
            page_id='ig_123',
            platform='instagram',
            sender_id='commenter_1',
            sender_name='Comment User',
            message_text='please send the guide',
            event_type='comment',
            comment_id='comment_123',
            post_id='post_999',
            raw_event={'field': 'feed'},
        )

        log = MessageLog.objects.get(comment_id='comment_123')
        self.assertEqual(log.trigger_matched, self.comment_trigger)
        self.assertTrue(log.reply_sent)
        self.assertEqual(log.post_id, 'post_999')
        mock_private_reply.assert_called_once()

    @patch('apps.social.tasks.send_message')
    @patch('apps.social.tasks.get_user_profile')
    def test_campaign_enrollment(self, mock_profile, mock_send):
        mock_profile.return_value = {'name': 'Bob Jones'}
        mock_send.return_value = {'success': True}

        campaign = Campaign.objects.create(name="Condo Drip", team=self.team)
        self.message_trigger.campaign = campaign
        self.message_trigger.save()

        process_incoming_event(
            page_id='page_123',
            platform='instagram',
            sender_id='user_enroll',
            message_text='I love Condos!',
            event_type='message',
        )

        contact = Contact.objects.get(custom_fields__instagram_id='user_enroll')
        self.assertTrue(
            campaign.enrollments.filter(contact=contact, is_active=True).exists()
        )

    @patch('apps.social.tasks.send_private_reply')
    def test_comment_without_comment_id_logs_reply_error(self, mock_private_reply):
        process_incoming_event(
            page_id='ig_123',
            platform='instagram',
            sender_id='commenter_2',
            sender_name='Comment User',
            message_text='guide please',
            event_type='comment',
        )

        log = MessageLog.objects.get(sender_id='commenter_2')
        self.assertFalse(log.reply_sent)
        self.assertIn('comment_id', log.reply_error)
        mock_private_reply.assert_not_called()
