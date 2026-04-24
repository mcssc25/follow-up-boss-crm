from django.test import TestCase, override_settings

from apps.accounts.models import Team, User
from apps.api.lead_routing import round_robin_assign


class RoundRobinAssignTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test")
        self.dave = User.objects.create_user(username="dave", password="x", team=self.team)
        self.kelly = User.objects.create_user(username="kelly", password="x", team=self.team)
        self.kerri = User.objects.create_user(username="kerri", password="x", team=self.team)
        self.outsider = User.objects.create_user(username="someone_else", password="x", team=self.team)

    @override_settings(TRACK_AGENTS={'track1': ['dave', 'kelly'], 'track2': ['kelly', 'kerri']})
    def test_track1_only_assigns_dave_or_kelly(self):
        for _ in range(20):
            assigned = round_robin_assign(self.team, track='track1')
            self.assertIn(assigned.username, ['dave', 'kelly'])

    @override_settings(TRACK_AGENTS={'track1': ['dave', 'kelly'], 'track2': ['kelly', 'kerri']})
    def test_track2_only_assigns_kelly_or_kerri(self):
        for _ in range(20):
            assigned = round_robin_assign(self.team, track='track2')
            self.assertIn(assigned.username, ['kelly', 'kerri'])

    def test_no_track_falls_back_to_existing_round_robin(self):
        # Without a track, any active team member is eligible
        assigned = round_robin_assign(self.team)
        self.assertIn(assigned.username, ['dave', 'kelly', 'kerri', 'someone_else'])

    @override_settings(TRACK_AGENTS={'track1': ['nobody']})
    def test_track_with_no_matching_users_returns_none(self):
        assigned = round_robin_assign(self.team, track='track1')
        self.assertIsNone(assigned)
