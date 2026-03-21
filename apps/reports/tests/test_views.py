from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import Team, User
from apps.campaigns.models import Campaign, CampaignEnrollment, CampaignStep
from apps.contacts.models import Contact, ContactActivity
from apps.pipeline.models import Deal, Pipeline, PipelineStage
from apps.tasks.models import Task


class ReportViewTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.user = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )
        self.client = Client()
        self.client.login(username="agent", password="pass")

    def test_report_index_loads(self):
        response = self.client.get('/reports/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lead Sources")
        self.assertContains(response, "Pipeline Conversion")
        self.assertContains(response, "Agent Activity")
        self.assertContains(response, "Campaign Performance")

    def test_lead_source_report(self):
        Contact.objects.create(
            first_name="Alice", last_name="A",
            source="zillow", team=self.team,
        )
        Contact.objects.create(
            first_name="Bob", last_name="B",
            source="zillow", team=self.team,
        )
        Contact.objects.create(
            first_name="Carol", last_name="C",
            source="referral", team=self.team,
        )

        response = self.client.get('/reports/lead-sources/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lead Source Report")
        self.assertContains(response, "Zillow")
        self.assertContains(response, "Referral")

    def test_lead_source_report_date_filter(self):
        response = self.client.get('/reports/lead-sources/?days=7')
        self.assertEqual(response.status_code, 200)

    def test_conversion_report(self):
        pipeline = Pipeline.objects.create(name="Sales", team=self.team)
        stage1 = PipelineStage.objects.create(
            pipeline=pipeline, name="Lead", order=1,
        )
        stage2 = PipelineStage.objects.create(
            pipeline=pipeline, name="Qualified", order=2,
        )
        contact = Contact.objects.create(
            first_name="Test", last_name="Contact", team=self.team,
        )
        Deal.objects.create(
            contact=contact, pipeline=pipeline, stage=stage1,
            title="Deal 1", value=100000,
        )

        response = self.client.get('/reports/conversion/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pipeline Conversion")
        self.assertContains(response, "Lead")
        self.assertContains(response, "Qualified")

    def test_conversion_report_pipeline_filter(self):
        pipeline = Pipeline.objects.create(name="Sales", team=self.team)
        PipelineStage.objects.create(
            pipeline=pipeline, name="Lead", order=1,
        )
        response = self.client.get(f'/reports/conversion/?pipeline={pipeline.pk}')
        self.assertEqual(response.status_code, 200)

    def test_agent_activity_report(self):
        contact = Contact.objects.create(
            first_name="Test", last_name="Contact",
            team=self.team, assigned_to=self.user,
        )
        ContactActivity.objects.create(
            contact=contact,
            activity_type='email_sent',
            description='Test email',
        )
        Task.objects.create(
            title="Test Task",
            assigned_to=self.user,
            team=self.team,
            due_date=timezone.now(),
            status='completed',
            completed_at=timezone.now(),
        )

        response = self.client.get('/reports/agent-activity/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agent Activity")
        self.assertContains(response, "agent")

    def test_campaign_performance_report(self):
        campaign = Campaign.objects.create(
            name="Test Campaign",
            team=self.team,
            created_by=self.user,
            is_active=True,
        )
        contact = Contact.objects.create(
            first_name="Test", last_name="Contact", team=self.team,
        )
        step = CampaignStep.objects.create(
            campaign=campaign, order=1, subject="Hi", body="Hello",
        )
        CampaignEnrollment.objects.create(
            contact=contact,
            campaign=campaign,
            current_step=step,
        )

        response = self.client.get('/reports/campaign-performance/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Campaign Performance")
        self.assertContains(response, "Test Campaign")
