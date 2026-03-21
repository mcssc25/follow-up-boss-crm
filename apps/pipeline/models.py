from django.conf import settings
from django.db import models
from django.urls import reverse


class Pipeline(models.Model):
    name = models.CharField(max_length=100)
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='pipelines',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('pipeline:board', kwargs={'pk': self.pk})


class PipelineStage(models.Model):
    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.CASCADE,
        related_name='stages',
    )
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField()
    color = models.CharField(max_length=7, default='#6366f1')

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.pipeline.name} - {self.name}"


class Deal(models.Model):
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.CASCADE,
        related_name='deals',
    )
    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.CASCADE,
        related_name='deals',
    )
    stage = models.ForeignKey(
        PipelineStage,
        on_delete=models.CASCADE,
        related_name='deals',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deals',
    )
    title = models.CharField(max_length=200, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expected_close_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    won = models.BooleanField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f"Deal #{self.pk} - {self.contact}"

    def get_absolute_url(self):
        return reverse('pipeline:deal_edit', kwargs={'pk': self.pk})
