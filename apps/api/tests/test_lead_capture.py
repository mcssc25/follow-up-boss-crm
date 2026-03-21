import json

from django.test import TestCase

from apps.accounts.models import Team, User
from apps.api.models import APIKey
from apps.campaigns.models import Campaign, CampaignStep
from apps.contacts.models import Contact


class LeadCaptureAPITest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.agent1 = User.objects.create_user(
            username="agent1", password="pass", team=self.team
        )
        self.agent2 = User.objects.create_user(
            username="agent2", password="pass", team=self.team
        )
        self.api_key = APIKey.objects.create(team=self.team, name="Test Key")

    def test_capture_lead(self):
        response = self.client.post(
            '/api/leads/',
            json.dumps({
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john@example.com',
            }),
            content_type='application/json',
            HTTP_X_API_KEY=self.api_key.key,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Contact.objects.filter(email='john@example.com').exists())

    def test_invalid_api_key(self):
        response = self.client.post(
            '/api/leads/',
            json.dumps({'first_name': 'John'}),
            content_type='application/json',
            HTTP_X_API_KEY='invalid',
        )
        self.assertEqual(response.status_code, 401)

    def test_round_robin_assignment(self):
        for i in range(4):
            self.client.post(
                '/api/leads/',
                json.dumps({
                    'first_name': f'Lead{i}',
                    'last_name': 'Test',
                    'email': f'lead{i}@test.com',
                }),
                content_type='application/json',
                HTTP_X_API_KEY=self.api_key.key,
            )
        self.assertEqual(
            Contact.objects.filter(assigned_to=self.agent1).count(), 2
        )
        self.assertEqual(
            Contact.objects.filter(assigned_to=self.agent2).count(), 2
        )

    def test_auto_enroll_campaign(self):
        campaign = Campaign.objects.create(
            name="Default", team=self.team, created_by=self.agent1
        )
        CampaignStep.objects.create(
            campaign=campaign,
            order=1,
            delay_days=0,
            delay_hours=0,
            subject="Welcome",
            body="Hi",
        )
        response = self.client.post(
            '/api/leads/',
            json.dumps({
                'first_name': 'Jane',
                'email': 'jane@test.com',
                'campaign_id': campaign.id,
            }),
            content_type='application/json',
            HTTP_X_API_KEY=self.api_key.key,
        )
        self.assertEqual(response.status_code, 201)
        contact = Contact.objects.get(email='jane@test.com')
        self.assertTrue(contact.enrollments.filter(campaign=campaign).exists())
