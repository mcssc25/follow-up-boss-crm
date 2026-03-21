from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Team, User
from apps.campaigns.models import Campaign, CampaignEnrollment, CampaignStep
from apps.contacts.models import Contact, ContactActivity


class CampaignViewTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Realty")
        self.user = User.objects.create_user(
            username="agent1",
            password="testpass123",
            team=self.team,
        )
        self.client.login(username="agent1", password="testpass123")

        self.campaign = Campaign.objects.create(
            name="Buyer Follow Up",
            description="Drip campaign for buyer leads",
            team=self.team,
            created_by=self.user,
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
            delay_hours=12,
            subject="Following up",
            body="<p>Just checking in.</p>",
        )
        self.contact = Contact.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            team=self.team,
        )

    def test_campaign_list(self):
        response = self.client.get(reverse('campaigns:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Buyer Follow Up")
        self.assertIn('campaigns', response.context)

        # Campaigns from another team should not appear
        other_team = Team.objects.create(name="Other Realty")
        Campaign.objects.create(name="Secret Campaign", team=other_team)
        response = self.client.get(reverse('campaigns:list'))
        self.assertNotContains(response, "Secret Campaign")

    def test_create_campaign(self):
        url = reverse('campaigns:create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(url, {
            'name': 'Seller Drip',
            'description': 'For seller leads',
        })
        self.assertEqual(response.status_code, 302)
        new_campaign = Campaign.objects.get(name='Seller Drip')
        self.assertEqual(new_campaign.team, self.team)
        self.assertEqual(new_campaign.created_by, self.user)

    def test_campaign_detail_shows_steps(self):
        response = self.client.get(
            reverse('campaigns:detail', kwargs={'pk': self.campaign.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Buyer Follow Up")
        self.assertContains(response, "Welcome")
        self.assertContains(response, "Following up")
        self.assertIn('steps', response.context)
        self.assertEqual(len(response.context['steps']), 2)

    def test_add_step(self):
        url = reverse('campaigns:add_step', kwargs={'pk': self.campaign.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(url, {
            'order': 3,
            'delay_days': 2,
            'delay_hours': 0,
            'subject': 'Any questions?',
            'body': '<p>Let me know if you have questions.</p>',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.campaign.steps.count(), 3)
        new_step = self.campaign.steps.get(order=3)
        self.assertEqual(new_step.subject, 'Any questions?')

    def test_edit_step(self):
        url = reverse('campaigns:edit_step', kwargs={'pk': self.step1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(url, {
            'order': 1,
            'delay_days': 0,
            'delay_hours': 1,
            'subject': 'Updated Welcome!',
            'body': '<p>Updated body.</p>',
        })
        self.assertEqual(response.status_code, 302)
        self.step1.refresh_from_db()
        self.assertEqual(self.step1.subject, 'Updated Welcome!')
        self.assertEqual(self.step1.delay_hours, 1)

    def test_delete_step(self):
        url = reverse('campaigns:delete_step', kwargs={'pk': self.step2.pk})

        # GET should not be allowed
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

        # POST should delete
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.campaign.steps.count(), 1)
        self.assertFalse(CampaignStep.objects.filter(pk=self.step2.pk).exists())

    def test_toggle_campaign(self):
        url = reverse('campaigns:toggle', kwargs={'pk': self.campaign.pk})

        # GET should not be allowed
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

        # Deactivate
        self.assertTrue(self.campaign.is_active)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.campaign.refresh_from_db()
        self.assertFalse(self.campaign.is_active)

        # Re-activate
        response = self.client.post(url)
        self.campaign.refresh_from_db()
        self.assertTrue(self.campaign.is_active)

    def test_duplicate_campaign(self):
        url = reverse('campaigns:duplicate', kwargs={'pk': self.campaign.pk})

        # GET should not be allowed
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        dup = Campaign.objects.get(name="Buyer Follow Up (Copy)")
        self.assertEqual(dup.team, self.team)
        self.assertFalse(dup.is_active)
        self.assertEqual(dup.steps.count(), 2)

    def test_enroll_contact(self):
        url = reverse('campaigns:enroll')

        # GET should not be allowed
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

        response = self.client.post(url, {
            'contact_id': self.contact.pk,
            'campaign_id': self.campaign.pk,
        })
        self.assertEqual(response.status_code, 302)
        enrollment = CampaignEnrollment.objects.get(
            contact=self.contact, campaign=self.campaign
        )
        self.assertTrue(enrollment.is_active)
        self.assertEqual(enrollment.current_step, self.step1)

        # Enrolling again should warn, not create duplicate
        response = self.client.post(url, {
            'contact_id': self.contact.pk,
            'campaign_id': self.campaign.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            CampaignEnrollment.objects.filter(
                contact=self.contact, campaign=self.campaign
            ).count(),
            1,
        )

    def test_unenroll_contact(self):
        enrollment = CampaignEnrollment.objects.create(
            contact=self.contact,
            campaign=self.campaign,
            current_step=self.step1,
        )
        url = reverse('campaigns:unenroll', kwargs={'pk': enrollment.pk})

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        enrollment.refresh_from_db()
        self.assertFalse(enrollment.is_active)

    def test_login_required(self):
        """Unauthenticated users should be redirected to login."""
        self.client.logout()
        urls = [
            reverse('campaigns:list'),
            reverse('campaigns:create'),
            reverse('campaigns:detail', kwargs={'pk': self.campaign.pk}),
            reverse('campaigns:edit', kwargs={'pk': self.campaign.pk}),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('login', response.url)

    def test_team_scoping(self):
        """Users should not see campaigns from other teams."""
        other_team = Team.objects.create(name="Other Realty")
        other_campaign = Campaign.objects.create(
            name="Other Campaign", team=other_team
        )
        response = self.client.get(
            reverse('campaigns:detail', kwargs={'pk': other_campaign.pk})
        )
        self.assertEqual(response.status_code, 404)


class VideoPlayerViewTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Realty")
        self.user = User.objects.create_user(
            username="agent1",
            password="testpass123",
            team=self.team,
        )
        self.campaign = Campaign.objects.create(
            name="Video Campaign",
            description="Campaign with video steps",
            team=self.team,
            created_by=self.user,
        )
        # Create a step with a video file
        fake_video = SimpleUploadedFile(
            "test_video.mp4",
            b"fake-video-content",
            content_type="video/mp4",
        )
        self.step = CampaignStep.objects.create(
            campaign=self.campaign,
            order=1,
            delay_days=0,
            delay_hours=0,
            subject="Watch this property tour",
            body="<p>Check out the video.</p>",
            video_file=fake_video,
        )
        self.contact = Contact.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            team=self.team,
        )

    def test_video_page_loads(self):
        """Video player page should load without authentication."""
        self.client.logout()
        url = reverse(
            'campaigns:video_player',
            kwargs={'step_id': self.step.pk, 'contact_id': self.contact.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Watch this property tour')
        self.assertContains(response, '<video')

    def test_video_logs_activity(self):
        """Visiting the video page should create a video_viewed activity."""
        self.client.logout()
        url = reverse(
            'campaigns:video_player',
            kwargs={'step_id': self.step.pk, 'contact_id': self.contact.pk},
        )
        self.client.get(url)
        activity = ContactActivity.objects.filter(
            contact=self.contact,
            activity_type='video_viewed',
        )
        self.assertEqual(activity.count(), 1)
        self.assertIn('Watch this property tour', activity.first().description)
        self.assertEqual(activity.first().metadata['step_id'], self.step.id)
        self.assertEqual(
            activity.first().metadata['campaign_id'], self.campaign.id,
        )

    def test_video_page_404_invalid_ids(self):
        """Invalid step or contact IDs should return 404."""
        url = reverse(
            'campaigns:video_player',
            kwargs={'step_id': 99999, 'contact_id': self.contact.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_video_track_endpoint(self):
        """Video tracking endpoint should accept POST with duration data."""
        self.client.logout()
        # First visit the page to create an activity
        player_url = reverse(
            'campaigns:video_player',
            kwargs={'step_id': self.step.pk, 'contact_id': self.contact.pk},
        )
        self.client.get(player_url)

        # Send tracking data
        track_url = reverse(
            'campaigns:video_track',
            kwargs={'step_id': self.step.pk, 'contact_id': self.contact.pk},
        )
        response = self.client.post(
            track_url,
            data='{"duration": 45, "percent": 75}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})

        # Check that the activity was updated
        activity = ContactActivity.objects.filter(
            contact=self.contact,
            activity_type='video_viewed',
        ).first()
        self.assertEqual(activity.metadata['watch_duration'], 45)
        self.assertEqual(activity.metadata['watch_percent'], 75)

    def test_video_track_rejects_get(self):
        """Video tracking endpoint should reject GET requests."""
        url = reverse(
            'campaigns:video_track',
            kwargs={'step_id': self.step.pk, 'contact_id': self.contact.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
