from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Team, User
from apps.contacts.models import Contact, SmartList
from apps.pipeline.models import Deal, Pipeline, PipelineStage


class SmartListModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name='Test Team')
        self.user = User.objects.create_user(
            username='agent1',
            email='agent1@test.com',
            password='testpass123',
            team=self.team,
        )

    def _make_contact(self, **kwargs):
        defaults = {
            'first_name': 'John',
            'last_name': 'Doe',
            'team': self.team,
        }
        defaults.update(kwargs)
        return Contact.objects.create(**defaults)

    def test_filter_by_source(self):
        c1 = self._make_contact(first_name='Zillow', source='zillow')
        c2 = self._make_contact(first_name='Manual', source='manual')

        sl = SmartList.objects.create(
            name='Zillow Leads',
            team=self.team,
            filters={'source': 'zillow'},
        )
        contacts = sl.get_contacts()
        self.assertIn(c1, contacts)
        self.assertNotIn(c2, contacts)

    def test_filter_no_contact_30_days(self):
        c_old = self._make_contact(
            first_name='Old',
            last_contacted_at=timezone.now() - timedelta(days=45),
        )
        c_recent = self._make_contact(
            first_name='Recent',
            last_contacted_at=timezone.now() - timedelta(days=5),
        )
        c_never = self._make_contact(
            first_name='Never',
            last_contacted_at=None,
        )

        sl = SmartList.objects.create(
            name='Cold Leads',
            team=self.team,
            filters={'last_contacted_days_ago_gt': 30},
        )
        contacts = sl.get_contacts()
        self.assertIn(c_old, contacts)
        self.assertIn(c_never, contacts)
        self.assertNotIn(c_recent, contacts)

    def test_filter_created_within_days(self):
        c_new = self._make_contact(first_name='New')
        # Manually backdate the old contact
        c_old = self._make_contact(first_name='Old')
        Contact.objects.filter(pk=c_old.pk).update(
            created_at=timezone.now() - timedelta(days=60),
        )

        sl = SmartList.objects.create(
            name='New Leads',
            team=self.team,
            filters={'created_days_ago_lt': 7},
        )
        contacts = sl.get_contacts()
        self.assertIn(c_new, contacts)
        self.assertNotIn(Contact.objects.get(pk=c_old.pk), contacts)

    def test_filter_by_assigned_to(self):
        other = User.objects.create_user(
            username='agent2', email='agent2@test.com',
            password='testpass123', team=self.team,
        )
        c1 = self._make_contact(first_name='A', assigned_to=self.user)
        c2 = self._make_contact(first_name='B', assigned_to=other)

        sl = SmartList.objects.create(
            name='My Leads',
            team=self.team,
            filters={'assigned_to': self.user.pk},
        )
        contacts = sl.get_contacts()
        self.assertIn(c1, contacts)
        self.assertNotIn(c2, contacts)

    def test_filter_no_deal(self):
        c_with_deal = self._make_contact(first_name='HasDeal')
        c_no_deal = self._make_contact(first_name='NoDeal')

        pipeline = Pipeline.objects.create(name='Sales', team=self.team)
        stage = PipelineStage.objects.create(pipeline=pipeline, name='New', order=1)
        Deal.objects.create(
            contact=c_with_deal,
            pipeline=pipeline,
            stage=stage,
        )

        sl = SmartList.objects.create(
            name='No Deal',
            team=self.team,
            filters={'no_deal': True},
        )
        contacts = sl.get_contacts()
        self.assertIn(c_no_deal, contacts)
        self.assertNotIn(c_with_deal, contacts)

    def test_filter_has_deal_in_stage(self):
        c1 = self._make_contact(first_name='InStage')
        c2 = self._make_contact(first_name='Other')

        pipeline = Pipeline.objects.create(name='Sales', team=self.team)
        stage1 = PipelineStage.objects.create(pipeline=pipeline, name='New', order=1)
        stage2 = PipelineStage.objects.create(pipeline=pipeline, name='Won', order=2)
        Deal.objects.create(contact=c1, pipeline=pipeline, stage=stage1)
        Deal.objects.create(contact=c2, pipeline=pipeline, stage=stage2)

        sl = SmartList.objects.create(
            name='In New Stage',
            team=self.team,
            filters={'has_deal_in_stage': stage1.pk},
        )
        contacts = sl.get_contacts()
        self.assertIn(c1, contacts)
        self.assertNotIn(c2, contacts)

    def test_multiple_filters_combined(self):
        c_match = self._make_contact(
            first_name='Match', source='zillow', assigned_to=self.user,
        )
        c_wrong_source = self._make_contact(
            first_name='Wrong', source='manual', assigned_to=self.user,
        )

        sl = SmartList.objects.create(
            name='Combined',
            team=self.team,
            filters={'source': 'zillow', 'assigned_to': self.user.pk},
        )
        contacts = sl.get_contacts()
        self.assertIn(c_match, contacts)
        self.assertNotIn(c_wrong_source, contacts)


class SmartListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.team = Team.objects.create(name='Test Team')
        self.user = User.objects.create_user(
            username='agent1',
            email='agent1@test.com',
            password='testpass123',
            team=self.team,
        )
        self.client.login(username='agent1', password='testpass123')

    def test_smart_list_list_view(self):
        SmartList.objects.create(name='Hot Leads', team=self.team, filters={})
        response = self.client.get(reverse('contacts:smart_list_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hot Leads')

    def test_smart_list_view_shows_matching_contacts(self):
        Contact.objects.create(
            first_name='Jane', last_name='Doe',
            source='zillow', team=self.team,
        )
        Contact.objects.create(
            first_name='Bob', last_name='Smith',
            source='manual', team=self.team,
        )
        sl = SmartList.objects.create(
            name='Zillow Only',
            team=self.team,
            filters={'source': 'zillow'},
        )
        response = self.client.get(
            reverse('contacts:smart_list_detail', args=[sl.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jane')
        self.assertNotContains(response, 'Bob')

    def test_create_smart_list(self):
        response = self.client.post(
            reverse('contacts:smart_list_create'),
            {'name': 'New List', 'source': 'referral'},
        )
        self.assertEqual(response.status_code, 302)
        sl = SmartList.objects.get(name='New List')
        self.assertEqual(sl.filters['source'], 'referral')
        self.assertEqual(sl.team, self.team)

    def test_create_smart_list_empty_filters_ignored(self):
        response = self.client.post(
            reverse('contacts:smart_list_create'),
            {'name': 'All Contacts'},
        )
        self.assertEqual(response.status_code, 302)
        sl = SmartList.objects.get(name='All Contacts')
        self.assertEqual(sl.filters, {})

    def test_smart_list_team_isolation(self):
        other_team = Team.objects.create(name='Other Team')
        sl = SmartList.objects.create(
            name='Other List', team=other_team, filters={},
        )
        response = self.client.get(reverse('contacts:smart_list_list'))
        self.assertNotContains(response, 'Other List')

    def test_smart_list_delete(self):
        sl = SmartList.objects.create(
            name='Delete Me', team=self.team, filters={},
        )
        response = self.client.post(
            reverse('contacts:smart_list_delete', args=[sl.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SmartList.objects.filter(pk=sl.pk).exists())
