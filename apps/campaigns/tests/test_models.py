from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Team, User
from apps.campaigns.models import Campaign, CampaignEnrollment, CampaignStep
from apps.contacts.models import Contact


class CampaignModelTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Realty")
        self.user = User.objects.create_user(
            username="agent1",
            password="testpass123",
            team=self.team,
        )
        self.contact = Contact.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            team=self.team,
            assigned_to=self.user,
        )

    def _create_campaign_with_steps(self):
        campaign = Campaign.objects.create(
            name="Buyer Follow Up",
            description="Drip campaign for new buyer leads",
            team=self.team,
            created_by=self.user,
        )
        step1 = CampaignStep.objects.create(
            campaign=campaign,
            order=1,
            delay_days=0,
            delay_hours=0,
            subject="Welcome {{first_name}}!",
            body="<p>Hi {{first_name}}, thanks for reaching out.</p>",
        )
        step2 = CampaignStep.objects.create(
            campaign=campaign,
            order=2,
            delay_days=1,
            delay_hours=12,
            subject="Following up",
            body="<p>Just checking in, {{first_name}}.</p>",
        )
        step3 = CampaignStep.objects.create(
            campaign=campaign,
            order=3,
            delay_days=3,
            delay_hours=0,
            subject="Any questions?",
            body="<p>Let me know if you have questions.</p>",
        )
        return campaign, step1, step2, step3

    def test_create_campaign_with_steps(self):
        campaign, step1, step2, step3 = self._create_campaign_with_steps()

        self.assertEqual(campaign.name, "Buyer Follow Up")
        self.assertTrue(campaign.is_active)
        self.assertEqual(campaign.steps.count(), 3)
        self.assertEqual(str(campaign), "Buyer Follow Up")

        # Steps should be ordered by 'order' field
        steps = list(campaign.steps.all())
        self.assertEqual(steps[0], step1)
        self.assertEqual(steps[1], step2)
        self.assertEqual(steps[2], step3)

    def test_enroll_contact(self):
        campaign, step1, step2, step3 = self._create_campaign_with_steps()

        enrollment = CampaignEnrollment.objects.create(
            contact=self.contact,
            campaign=campaign,
            current_step=step1,
            next_send_at=timezone.now(),
        )

        self.assertTrue(enrollment.is_active)
        self.assertEqual(enrollment.current_step, step1)
        self.assertIsNone(enrollment.completed_at)
        self.assertEqual(self.contact.enrollments.count(), 1)

    def test_pause_on_reply(self):
        campaign, step1, step2, step3 = self._create_campaign_with_steps()

        enrollment = CampaignEnrollment.objects.create(
            contact=self.contact,
            campaign=campaign,
            current_step=step1,
            next_send_at=timezone.now(),
        )

        enrollment.pause("contact_replied")
        enrollment.refresh_from_db()

        self.assertFalse(enrollment.is_active)
        self.assertEqual(enrollment.paused_reason, "contact_replied")

    def test_resume_enrollment(self):
        campaign, step1, step2, step3 = self._create_campaign_with_steps()

        enrollment = CampaignEnrollment.objects.create(
            contact=self.contact,
            campaign=campaign,
            current_step=step1,
            is_active=False,
            paused_reason="contact_replied",
        )

        enrollment.resume()
        enrollment.refresh_from_db()

        self.assertTrue(enrollment.is_active)
        self.assertEqual(enrollment.paused_reason, "")
        self.assertIsNotNone(enrollment.next_send_at)

    def test_advance_to_next_step(self):
        campaign, step1, step2, step3 = self._create_campaign_with_steps()

        enrollment = CampaignEnrollment.objects.create(
            contact=self.contact,
            campaign=campaign,
            current_step=step1,
            next_send_at=timezone.now(),
        )

        enrollment.advance_to_next_step()
        enrollment.refresh_from_db()

        self.assertEqual(enrollment.current_step, step2)
        self.assertTrue(enrollment.is_active)
        self.assertIsNotNone(enrollment.next_send_at)
        # step2 has delay_days=1, delay_hours=12 => 36 hours total
        expected_min = timezone.now() + timedelta(hours=35)
        expected_max = timezone.now() + timedelta(hours=37)
        self.assertGreaterEqual(enrollment.next_send_at, expected_min)
        self.assertLessEqual(enrollment.next_send_at, expected_max)

    def test_advance_completes_when_no_more_steps(self):
        campaign, step1, step2, step3 = self._create_campaign_with_steps()

        enrollment = CampaignEnrollment.objects.create(
            contact=self.contact,
            campaign=campaign,
            current_step=step3,
            next_send_at=timezone.now(),
        )

        enrollment.advance_to_next_step()
        enrollment.refresh_from_db()

        self.assertFalse(enrollment.is_active)
        self.assertIsNotNone(enrollment.completed_at)

    def test_duplicate_campaign(self):
        campaign, step1, step2, step3 = self._create_campaign_with_steps()

        new_campaign = campaign.duplicate()

        self.assertEqual(new_campaign.name, "Buyer Follow Up (Copy)")
        self.assertFalse(new_campaign.is_active)
        self.assertEqual(new_campaign.team, self.team)
        self.assertEqual(new_campaign.created_by, self.user)
        self.assertEqual(new_campaign.steps.count(), 3)

        # Verify steps were copied correctly
        new_steps = list(new_campaign.steps.all())
        self.assertEqual(new_steps[0].order, 1)
        self.assertEqual(new_steps[0].subject, "Welcome {{first_name}}!")
        self.assertEqual(new_steps[1].delay_days, 1)
        self.assertEqual(new_steps[1].delay_hours, 12)

        # Originals should be unchanged
        self.assertEqual(campaign.steps.count(), 3)
        self.assertNotEqual(new_campaign.pk, campaign.pk)

    def test_total_delay_hours(self):
        campaign = Campaign.objects.create(
            name="Test",
            team=self.team,
            created_by=self.user,
        )
        step = CampaignStep.objects.create(
            campaign=campaign,
            order=1,
            delay_days=2,
            delay_hours=6,
            subject="Test",
            body="<p>Test</p>",
        )

        self.assertEqual(step.total_delay_hours, 54)  # (2 * 24) + 6
