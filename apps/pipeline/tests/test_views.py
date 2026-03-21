import json

from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import Team, User
from apps.contacts.models import Contact, ContactActivity
from apps.pipeline.models import Deal, Pipeline, PipelineStage


class PipelineViewTestBase(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.user = User.objects.create_user(
            username="agent", password="testpass123", team=self.team
        )
        self.client = Client()
        self.client.login(username="agent", password="testpass123")

        self.contact = Contact.objects.create(
            first_name="Jane", last_name="Smith", team=self.team
        )
        self.pipeline = Pipeline.objects.create(name="Sales", team=self.team)
        self.stage1 = PipelineStage.objects.create(
            pipeline=self.pipeline, name="Lead", order=1, color="#3b82f6"
        )
        self.stage2 = PipelineStage.objects.create(
            pipeline=self.pipeline, name="Qualified", order=2, color="#10b981"
        )


class PipelineListViewTest(PipelineViewTestBase):
    def test_pipeline_list_loads(self):
        response = self.client.get(reverse('pipeline:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sales")

    def test_pipeline_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('pipeline:list'))
        self.assertEqual(response.status_code, 302)

    def test_pipeline_list_filters_by_team(self):
        other_team = Team.objects.create(name="Other Team")
        Pipeline.objects.create(name="Other Pipeline", team=other_team)
        response = self.client.get(reverse('pipeline:list'))
        self.assertContains(response, "Sales")
        self.assertNotContains(response, "Other Pipeline")


class PipelineBoardViewTest(PipelineViewTestBase):
    def test_board_loads(self):
        response = self.client.get(
            reverse('pipeline:board', kwargs={'pk': self.pipeline.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lead")
        self.assertContains(response, "Qualified")

    def test_board_shows_deals(self):
        Deal.objects.create(
            contact=self.contact,
            pipeline=self.pipeline,
            stage=self.stage1,
            title="Test Property",
            value=250000,
        )
        response = self.client.get(
            reverse('pipeline:board', kwargs={'pk': self.pipeline.pk})
        )
        self.assertContains(response, "Jane Smith")
        self.assertContains(response, "Test Property")

    def test_board_other_team_404(self):
        other_team = Team.objects.create(name="Other Team")
        other_pipeline = Pipeline.objects.create(name="Other", team=other_team)
        response = self.client.get(
            reverse('pipeline:board', kwargs={'pk': other_pipeline.pk})
        )
        self.assertEqual(response.status_code, 404)


class MoveDealViewTest(PipelineViewTestBase):
    def test_move_deal_api(self):
        deal = Deal.objects.create(
            contact=self.contact,
            pipeline=self.pipeline,
            stage=self.stage1,
            title="Test Deal",
        )
        response = self.client.post(
            reverse('pipeline:deal_move', kwargs={'pk': deal.pk}),
            data=json.dumps({'stage_id': self.stage2.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        deal.refresh_from_db()
        self.assertEqual(deal.stage, self.stage2)

    def test_move_deal_logs_activity(self):
        deal = Deal.objects.create(
            contact=self.contact,
            pipeline=self.pipeline,
            stage=self.stage1,
            title="Test Deal",
        )
        self.client.post(
            reverse('pipeline:deal_move', kwargs={'pk': deal.pk}),
            data=json.dumps({'stage_id': self.stage2.pk}),
            content_type='application/json',
        )
        activity = ContactActivity.objects.filter(
            contact=self.contact,
            activity_type='stage_changed',
        ).first()
        self.assertIsNotNone(activity)
        self.assertIn('Lead', activity.description)
        self.assertIn('Qualified', activity.description)

    def test_move_deal_invalid_stage(self):
        deal = Deal.objects.create(
            contact=self.contact,
            pipeline=self.pipeline,
            stage=self.stage1,
        )
        response = self.client.post(
            reverse('pipeline:deal_move', kwargs={'pk': deal.pk}),
            data=json.dumps({'stage_id': 99999}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_move_deal_get_not_allowed(self):
        deal = Deal.objects.create(
            contact=self.contact,
            pipeline=self.pipeline,
            stage=self.stage1,
        )
        response = self.client.get(
            reverse('pipeline:deal_move', kwargs={'pk': deal.pk})
        )
        self.assertEqual(response.status_code, 405)

    def test_move_deal_missing_stage_id(self):
        deal = Deal.objects.create(
            contact=self.contact,
            pipeline=self.pipeline,
            stage=self.stage1,
        )
        response = self.client.post(
            reverse('pipeline:deal_move', kwargs={'pk': deal.pk}),
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class DealCreateViewTest(PipelineViewTestBase):
    def test_deal_create_form_loads(self):
        response = self.client.get(
            reverse('pipeline:deal_create') + f'?pipeline={self.pipeline.pk}'
        )
        self.assertEqual(response.status_code, 200)

    def test_deal_create_success(self):
        response = self.client.post(
            reverse('pipeline:deal_create') + f'?pipeline={self.pipeline.pk}',
            data={
                'pipeline': self.pipeline.pk,
                'contact': self.contact.pk,
                'stage': self.stage1.pk,
                'title': 'New Property Deal',
                'value': '500000.00',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Deal.objects.count(), 1)
        deal = Deal.objects.first()
        self.assertEqual(deal.title, 'New Property Deal')


class DealUpdateViewTest(PipelineViewTestBase):
    def test_deal_edit_loads(self):
        deal = Deal.objects.create(
            contact=self.contact,
            pipeline=self.pipeline,
            stage=self.stage1,
            title="Existing Deal",
        )
        response = self.client.get(
            reverse('pipeline:deal_edit', kwargs={'pk': deal.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Existing Deal")

    def test_deal_edit_success(self):
        deal = Deal.objects.create(
            contact=self.contact,
            pipeline=self.pipeline,
            stage=self.stage1,
            title="Old Title",
        )
        response = self.client.post(
            reverse('pipeline:deal_edit', kwargs={'pk': deal.pk}),
            data={
                'contact': self.contact.pk,
                'stage': self.stage2.pk,
                'title': 'Updated Title',
            },
        )
        self.assertEqual(response.status_code, 302)
        deal.refresh_from_db()
        self.assertEqual(deal.title, 'Updated Title')
        self.assertEqual(deal.stage, self.stage2)
