from django.test import TestCase

from apps.accounts.models import Team, User
from apps.contacts.models import Contact
from apps.pipeline.models import Deal, Pipeline, PipelineStage


class PipelineModelTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team")
        self.agent = User.objects.create_user(
            username="agent", password="pass", team=self.team
        )
        self.contact = Contact.objects.create(
            first_name="John", last_name="Doe", team=self.team
        )

    def test_create_pipeline(self):
        pipeline = Pipeline.objects.create(name="Sales Pipeline", team=self.team)
        self.assertEqual(str(pipeline), "Sales Pipeline")
        self.assertEqual(pipeline.team, self.team)

    def test_create_pipeline_with_stages(self):
        pipeline = Pipeline.objects.create(name="Sales Pipeline", team=self.team)
        stage1 = PipelineStage.objects.create(
            pipeline=pipeline, name="Lead", order=1, color="#3b82f6"
        )
        stage2 = PipelineStage.objects.create(
            pipeline=pipeline, name="Qualified", order=2, color="#10b981"
        )
        stage3 = PipelineStage.objects.create(
            pipeline=pipeline, name="Closed", order=3, color="#ef4444"
        )
        self.assertEqual(pipeline.stages.count(), 3)
        # Verify ordering
        stages = list(pipeline.stages.all())
        self.assertEqual(stages[0], stage1)
        self.assertEqual(stages[1], stage2)
        self.assertEqual(stages[2], stage3)

    def test_stage_str(self):
        pipeline = Pipeline.objects.create(name="Sales", team=self.team)
        stage = PipelineStage.objects.create(
            pipeline=pipeline, name="Lead", order=1
        )
        self.assertEqual(str(stage), "Sales - Lead")

    def test_create_deal(self):
        pipeline = Pipeline.objects.create(name="Sales", team=self.team)
        stage = PipelineStage.objects.create(
            pipeline=pipeline, name="Lead", order=1
        )
        deal = Deal.objects.create(
            contact=self.contact,
            pipeline=pipeline,
            stage=stage,
            assigned_to=self.agent,
            title="123 Main St",
            value=350000,
        )
        self.assertEqual(deal.contact, self.contact)
        self.assertEqual(deal.stage, stage)
        self.assertEqual(deal.value, 350000)
        self.assertIn("123 Main St", str(deal))

    def test_deal_str_without_title(self):
        pipeline = Pipeline.objects.create(name="Sales", team=self.team)
        stage = PipelineStage.objects.create(
            pipeline=pipeline, name="Lead", order=1
        )
        deal = Deal.objects.create(
            contact=self.contact,
            pipeline=pipeline,
            stage=stage,
        )
        self.assertIn("John Doe", str(deal))

    def test_move_deal_to_new_stage(self):
        pipeline = Pipeline.objects.create(name="Sales", team=self.team)
        stage1 = PipelineStage.objects.create(
            pipeline=pipeline, name="Lead", order=1
        )
        stage2 = PipelineStage.objects.create(
            pipeline=pipeline, name="Qualified", order=2
        )
        deal = Deal.objects.create(
            contact=self.contact,
            pipeline=pipeline,
            stage=stage1,
            title="Test Deal",
        )
        self.assertEqual(deal.stage, stage1)

        deal.stage = stage2
        deal.save()
        deal.refresh_from_db()
        self.assertEqual(deal.stage, stage2)

    def test_deal_defaults(self):
        pipeline = Pipeline.objects.create(name="Sales", team=self.team)
        stage = PipelineStage.objects.create(
            pipeline=pipeline, name="Lead", order=1
        )
        deal = Deal.objects.create(
            contact=self.contact,
            pipeline=pipeline,
            stage=stage,
        )
        self.assertIsNone(deal.value)
        self.assertIsNone(deal.expected_close_date)
        self.assertIsNone(deal.closed_at)
        self.assertIsNone(deal.won)
        self.assertIsNone(deal.assigned_to)

    def test_pipeline_cascade_delete(self):
        pipeline = Pipeline.objects.create(name="Sales", team=self.team)
        stage = PipelineStage.objects.create(
            pipeline=pipeline, name="Lead", order=1
        )
        Deal.objects.create(
            contact=self.contact,
            pipeline=pipeline,
            stage=stage,
        )
        pipeline.delete()
        self.assertEqual(PipelineStage.objects.count(), 0)
        self.assertEqual(Deal.objects.count(), 0)

    def test_stage_default_color(self):
        pipeline = Pipeline.objects.create(name="Sales", team=self.team)
        stage = PipelineStage.objects.create(
            pipeline=pipeline, name="Lead", order=1
        )
        self.assertEqual(stage.color, "#6366f1")
