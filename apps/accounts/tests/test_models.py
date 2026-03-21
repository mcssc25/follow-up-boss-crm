from django.test import TestCase

from apps.accounts.models import Team, User


class TeamModelTest(TestCase):
    def test_create_team(self):
        team = Team.objects.create(name="Test Team")
        self.assertEqual(str(team), "Test Team")
        self.assertIsNotNone(team.created_at)

    def test_team_ordering(self):
        Team.objects.create(name="Bravo")
        Team.objects.create(name="Alpha")
        teams = list(Team.objects.values_list('name', flat=True))
        self.assertEqual(teams, ["Alpha", "Bravo"])


class UserModelTest(TestCase):
    def test_create_user_with_role(self):
        team = Team.objects.create(name="Test Team")
        user = User.objects.create_user(
            username="agent1",
            email="agent1@test.com",
            password="testpass123",
            role="agent",
            team=team,
        )
        self.assertEqual(user.role, "agent")
        self.assertEqual(user.team, team)
        self.assertFalse(user.is_admin)

    def test_user_is_admin(self):
        user = User.objects.create_user(
            username="admin1",
            email="admin@test.com",
            password="testpass123",
            role="admin",
        )
        self.assertTrue(user.is_admin)

    def test_user_default_role(self):
        user = User.objects.create_user(
            username="default_user",
            password="testpass123",
        )
        self.assertEqual(user.role, "agent")

    def test_user_str_with_full_name(self):
        user = User.objects.create_user(
            username="jdoe",
            first_name="John",
            last_name="Doe",
            password="testpass123",
        )
        self.assertEqual(str(user), "John Doe")

    def test_user_str_without_full_name(self):
        user = User.objects.create_user(
            username="jdoe",
            password="testpass123",
        )
        self.assertEqual(str(user), "jdoe")

    def test_gmail_fields_default(self):
        user = User.objects.create_user(
            username="test_gmail",
            password="testpass123",
        )
        self.assertFalse(user.gmail_connected)
        self.assertEqual(user.gmail_access_token, "")
        self.assertEqual(user.gmail_refresh_token, "")
        self.assertIsNone(user.gmail_token_expiry)

    def test_team_members_related_name(self):
        team = Team.objects.create(name="Sales")
        user1 = User.objects.create_user(username="u1", password="p", team=team)
        user2 = User.objects.create_user(username="u2", password="p", team=team)
        self.assertEqual(set(team.members.all()), {user1, user2})
