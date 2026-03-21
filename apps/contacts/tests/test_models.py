from django.test import TestCase

from apps.accounts.models import Team, User
from apps.contacts.models import Contact, ContactActivity, ContactNote


class ContactModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.agent = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )

    def test_create_contact(self):
        contact = Contact.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="555-1234",
            source="landing_page",
            assigned_to=self.agent,
            team=self.team,
        )
        self.assertEqual(str(contact), "John Doe")
        self.assertEqual(contact.assigned_to, self.agent)

    def test_contact_defaults(self):
        contact = Contact.objects.create(
            first_name="Jane", last_name="Doe", team=self.team
        )
        self.assertEqual(contact.source, "manual")
        self.assertEqual(contact.tags, [])
        self.assertEqual(contact.custom_fields, {})
        self.assertIsNone(contact.last_contacted_at)

    def test_add_note(self):
        contact = Contact.objects.create(
            first_name="Jane", last_name="Doe", team=self.team
        )
        note = ContactNote.objects.create(
            contact=contact, author=self.agent, content="Called, left voicemail"
        )
        self.assertEqual(contact.notes.count(), 1)
        self.assertEqual(note.content, "Called, left voicemail")

    def test_log_activity(self):
        contact = Contact.objects.create(
            first_name="Jane", last_name="Doe", team=self.team
        )
        activity = ContactActivity.objects.create(
            contact=contact,
            activity_type="email_sent",
            description="Welcome email sent",
        )
        self.assertEqual(contact.activities.count(), 1)
        self.assertEqual(activity.activity_type, "email_sent")

    def test_contact_cascade_delete(self):
        contact = Contact.objects.create(
            first_name="Jane", last_name="Doe", team=self.team
        )
        ContactNote.objects.create(
            contact=contact, author=self.agent, content="Test note"
        )
        ContactActivity.objects.create(
            contact=contact, activity_type="call_logged"
        )
        contact.delete()
        self.assertEqual(ContactNote.objects.count(), 0)
        self.assertEqual(ContactActivity.objects.count(), 0)
