from django.test import Client, TestCase

from apps.accounts.models import Team, User
from apps.contacts.models import Contact, ContactActivity, ContactNote


class ContactViewTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.user = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )
        self.client = Client()
        self.client.login(username="agent", password="pass")

    def test_contact_list(self):
        Contact.objects.create(
            first_name="John", last_name="Doe",
            team=self.team, assigned_to=self.user,
        )
        response = self.client.get('/contacts/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "John Doe")

    def test_contact_list_search(self):
        Contact.objects.create(
            first_name="Alice", last_name="Wonder",
            email="alice@example.com", team=self.team,
        )
        Contact.objects.create(
            first_name="Bob", last_name="Builder",
            team=self.team,
        )
        response = self.client.get('/contacts/?q=alice')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Wonder")
        self.assertNotContains(response, "Bob Builder")

    def test_contact_list_filter_source(self):
        Contact.objects.create(
            first_name="A", last_name="B",
            source="zillow", team=self.team,
        )
        Contact.objects.create(
            first_name="C", last_name="D",
            source="manual", team=self.team,
        )
        response = self.client.get('/contacts/?source=zillow')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A B")
        self.assertNotContains(response, "C D")

    def test_create_contact(self):
        response = self.client.post('/contacts/create/', {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane@example.com',
            'source': 'manual',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Contact.objects.filter(last_name='Smith').exists())
        contact = Contact.objects.get(last_name='Smith')
        self.assertEqual(contact.team, self.team)

    def test_create_contact_sets_team(self):
        self.client.post('/contacts/create/', {
            'first_name': 'Auto',
            'last_name': 'Team',
            'source': 'manual',
        })
        contact = Contact.objects.get(last_name='Team')
        self.assertEqual(contact.team, self.team)

    def test_contact_detail(self):
        contact = Contact.objects.create(
            first_name="John", last_name="Doe", team=self.team,
        )
        response = self.client.get(f'/contacts/{contact.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "John Doe")

    def test_contact_detail_other_team(self):
        other_team = Team.objects.create(name="Other")
        contact = Contact.objects.create(
            first_name="Secret", last_name="Agent",
            team=other_team,
        )
        response = self.client.get(f'/contacts/{contact.id}/')
        self.assertEqual(response.status_code, 404)

    def test_edit_contact(self):
        contact = Contact.objects.create(
            first_name="Old", last_name="Name",
            team=self.team, source="manual",
        )
        response = self.client.post(f'/contacts/{contact.id}/edit/', {
            'first_name': 'New',
            'last_name': 'Name',
            'source': 'referral',
        })
        self.assertEqual(response.status_code, 302)
        contact.refresh_from_db()
        self.assertEqual(contact.first_name, 'New')
        self.assertEqual(contact.source, 'referral')

    def test_add_note(self):
        contact = Contact.objects.create(
            first_name="John", last_name="Doe", team=self.team,
        )
        response = self.client.post(f'/contacts/{contact.id}/note/', {
            'content': 'Test note content',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ContactNote.objects.filter(contact=contact).exists())
        self.assertTrue(
            ContactActivity.objects.filter(
                contact=contact, activity_type='note_added',
            ).exists()
        )

    def test_add_note_get_not_allowed(self):
        contact = Contact.objects.create(
            first_name="John", last_name="Doe", team=self.team,
        )
        response = self.client.get(f'/contacts/{contact.id}/note/')
        self.assertEqual(response.status_code, 405)

    def test_log_activity(self):
        contact = Contact.objects.create(
            first_name="John", last_name="Doe", team=self.team,
        )
        response = self.client.post(f'/contacts/{contact.id}/log-activity/', {
            'activity_type': 'call_logged',
            'description': 'Discussed pricing',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ContactActivity.objects.filter(
                contact=contact, activity_type='call_logged',
            ).exists()
        )

    def test_bulk_delete(self):
        c1 = Contact.objects.create(
            first_name="A", last_name="A", team=self.team,
        )
        c2 = Contact.objects.create(
            first_name="B", last_name="B", team=self.team,
        )
        response = self.client.post('/contacts/bulk-action/', {
            'action': 'delete',
            'contact_ids': [c1.pk, c2.pk],
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Contact.objects.count(), 0)

    def test_bulk_assign(self):
        c1 = Contact.objects.create(
            first_name="A", last_name="A", team=self.team,
        )
        response = self.client.post('/contacts/bulk-action/', {
            'action': 'assign',
            'contact_ids': [c1.pk],
            'assign_to': self.user.pk,
        })
        self.assertEqual(response.status_code, 302)
        c1.refresh_from_db()
        self.assertEqual(c1.assigned_to, self.user)

    def test_bulk_tag(self):
        c1 = Contact.objects.create(
            first_name="A", last_name="A", team=self.team,
        )
        response = self.client.post('/contacts/bulk-action/', {
            'action': 'tag',
            'contact_ids': [c1.pk],
            'tag': 'vip',
        })
        self.assertEqual(response.status_code, 302)
        c1.refresh_from_db()
        self.assertIn('vip', c1.tags)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get('/contacts/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url.lower() if response.url else '')
