from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Team, User
from apps.campaigns.email_renderer import render_campaign_email
from apps.campaigns.models import Campaign, CampaignEnrollment, CampaignStep
from apps.contacts.models import Contact, ContactActivity


class EmailRendererTest(TestCase):
    """Tests for the merge-field email renderer."""

    def setUp(self):
        self.team = Team.objects.create(name="Test Realty")
        self.agent = User.objects.create_user(
            username="agent1",
            email="agent@example.com",
            first_name="Mike",
            last_name="Smith",
            password="testpass123",
            team=self.team,
            phone="555-1234",
        )
        self.contact = Contact.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            team=self.team,
            assigned_to=self.agent,
        )

    def test_render_merge_fields(self):
        body = (
            "Hi {{first_name}} {{last_name}}, "
            "I'm {{agent_name}}. "
            "Call me at {{agent_phone}} or email {{agent_email}}. "
            "Full name: {{full_name}}."
        )
        result = render_campaign_email(body, self.contact, self.agent)

        self.assertIn("Jane", result)
        self.assertIn("Doe", result)
        self.assertIn("Mike Smith", result)
        self.assertIn("555-1234", result)
        self.assertIn("agent@example.com", result)
        self.assertIn("Jane Doe", result)
        self.assertNotIn("{{", result)

    def test_render_with_missing_agent_phone(self):
        self.agent.phone = ""
        self.agent.save()
        body = "Call {{agent_phone}} for help."
        result = render_campaign_email(body, self.contact, self.agent)
        self.assertNotIn("{{agent_phone}}", result)
        self.assertEqual(result, "Call  for help.")

    def test_render_agent_name_falls_back_to_username(self):
        self.agent.first_name = ""
        self.agent.last_name = ""
        self.agent.save()
        body = "From {{agent_name}}"
        result = render_campaign_email(body, self.contact, self.agent)
        self.assertIn("agent1", result)


class CampaignTaskTest(TestCase):
    """Tests for Celery tasks that power drip campaign sending."""

    def setUp(self):
        self.team = Team.objects.create(name="Test Realty")
        self.agent = User.objects.create_user(
            username="agent1",
            email="agent@example.com",
            first_name="Mike",
            last_name="Smith",
            password="testpass123",
            team=self.team,
            phone="555-1234",
            gmail_connected=True,
            gmail_access_token="fake-access-token",
            gmail_refresh_token="fake-refresh-token",
        )
        self.contact = Contact.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            team=self.team,
            assigned_to=self.agent,
        )
        self.campaign = Campaign.objects.create(
            name="Buyer Follow Up",
            team=self.team,
            created_by=self.agent,
        )
        self.step1 = CampaignStep.objects.create(
            campaign=self.campaign,
            order=1,
            delay_days=0,
            delay_hours=0,
            subject="Welcome {{first_name}}!",
            body="<p>Hi {{first_name}}, thanks for reaching out.</p>",
        )
        self.step2 = CampaignStep.objects.create(
            campaign=self.campaign,
            order=2,
            delay_days=1,
            delay_hours=0,
            subject="Following up",
            body="<p>Just checking in, {{first_name}}.</p>",
        )

    def _create_due_enrollment(self):
        return CampaignEnrollment.objects.create(
            contact=self.contact,
            campaign=self.campaign,
            current_step=self.step1,
            next_send_at=timezone.now() - timedelta(minutes=5),
        )

    @patch('apps.campaigns.tasks.GmailService')
    def test_process_due_emails_sends(self, mock_gmail_class):
        """Due enrollments should trigger email send and advance step."""
        mock_instance = MagicMock()
        mock_instance.send_email.return_value = {'success': True, 'message_id': 'abc123'}
        mock_gmail_class.return_value = mock_instance

        enrollment = self._create_due_enrollment()

        # Import here so the patch is active
        from apps.campaigns.tasks import process_due_emails, send_campaign_email

        # Call synchronously (bypass .delay) by calling send directly
        send_campaign_email(enrollment.id)

        mock_instance.send_email.assert_called_once()
        call_kwargs = mock_instance.send_email.call_args
        self.assertEqual(call_kwargs[1]['to'], 'jane@example.com')
        self.assertIn('Jane', call_kwargs[1]['subject'])

        # Enrollment should have advanced to step 2
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.current_step, self.step2)

    @patch('apps.campaigns.tasks.GmailService')
    def test_skips_inactive_enrollment(self, mock_gmail_class):
        """Paused enrollments should not send."""
        mock_instance = MagicMock()
        mock_gmail_class.return_value = mock_instance

        enrollment = self._create_due_enrollment()
        enrollment.pause("manual_pause")

        from apps.campaigns.tasks import send_campaign_email

        send_campaign_email(enrollment.id)

        mock_instance.send_email.assert_not_called()

    @patch('apps.campaigns.tasks.GmailService')
    def test_skips_no_gmail(self, mock_gmail_class):
        """Agent without gmail_connected should not send."""
        mock_instance = MagicMock()
        mock_gmail_class.return_value = mock_instance

        self.agent.gmail_connected = False
        self.agent.save()

        enrollment = self._create_due_enrollment()

        from apps.campaigns.tasks import send_campaign_email

        send_campaign_email(enrollment.id)

        mock_instance.send_email.assert_not_called()

    @patch('apps.campaigns.tasks.GmailService')
    def test_logs_activity_on_send(self, mock_gmail_class):
        """Successful send should create a ContactActivity record."""
        mock_instance = MagicMock()
        mock_instance.send_email.return_value = {'success': True, 'message_id': 'abc123'}
        mock_gmail_class.return_value = mock_instance

        enrollment = self._create_due_enrollment()

        from apps.campaigns.tasks import send_campaign_email

        send_campaign_email(enrollment.id)

        activity = ContactActivity.objects.filter(
            contact=self.contact,
            activity_type='email_sent',
        ).first()
        self.assertIsNotNone(activity)
        self.assertIn("Campaign email:", activity.description)
        self.assertEqual(activity.metadata['campaign_id'], self.campaign.id)
        self.assertEqual(activity.metadata['step_order'], 1)

        # last_contacted_at should be updated
        self.contact.refresh_from_db()
        self.assertIsNotNone(self.contact.last_contacted_at)

    @patch('apps.campaigns.tasks.GmailService')
    def test_does_not_log_on_failed_send(self, mock_gmail_class):
        """Failed send should not create activity or advance step."""
        mock_instance = MagicMock()
        mock_instance.send_email.return_value = {'success': False, 'error': 'Auth failed'}
        mock_gmail_class.return_value = mock_instance

        enrollment = self._create_due_enrollment()

        from apps.campaigns.tasks import send_campaign_email

        send_campaign_email(enrollment.id)

        self.assertEqual(
            ContactActivity.objects.filter(contact=self.contact).count(), 0
        )
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.current_step, self.step1)

    @patch('apps.campaigns.tasks.send_campaign_email')
    def test_process_due_emails_dispatches(self, mock_send_task):
        """process_due_emails should dispatch individual tasks for due enrollments."""
        enrollment = self._create_due_enrollment()

        # Also create a future enrollment that should NOT be dispatched
        CampaignEnrollment.objects.create(
            contact=self.contact,
            campaign=self.campaign,
            current_step=self.step1,
            next_send_at=timezone.now() + timedelta(hours=1),
        )

        from apps.campaigns.tasks import process_due_emails

        process_due_emails()

        mock_send_task.delay.assert_called_once_with(enrollment.id)
