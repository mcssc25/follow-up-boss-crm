from django import forms

from apps.campaigns.models import Campaign, CampaignStep

INPUT_CSS = (
    'mt-1 block w-full rounded-md border-gray-300 shadow-sm '
    'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
)


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['name', 'description', 'next_campaign']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': INPUT_CSS,
                'placeholder': 'e.g. Buyer Follow Up',
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': INPUT_CSS,
                'placeholder': 'Describe the purpose of this campaign...',
            }),
            'next_campaign': forms.Select(attrs={
                'class': INPUT_CSS,
            }),
        }
        labels = {
            'next_campaign': 'Next Campaign (auto-enroll on completion)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show campaigns from the same team; exclude self to prevent loops
        if self.instance and self.instance.pk:
            self.fields['next_campaign'].queryset = Campaign.objects.filter(
                team=self.instance.team,
            ).exclude(pk=self.instance.pk)
        else:
            # For new campaigns, we'll filter after team is set
            self.fields['next_campaign'].queryset = Campaign.objects.none()


class CampaignStepForm(forms.ModelForm):
    class Meta:
        model = CampaignStep
        fields = ['order', 'delay_days', 'delay_hours', 'subject', 'body', 'video_file', 'video']
        widgets = {
            'order': forms.NumberInput(attrs={
                'class': INPUT_CSS,
                'min': '1',
            }),
            'delay_days': forms.NumberInput(attrs={
                'class': INPUT_CSS,
                'min': '0',
            }),
            'delay_hours': forms.NumberInput(attrs={
                'class': INPUT_CSS,
                'min': '0',
            }),
            'subject': forms.TextInput(attrs={
                'class': INPUT_CSS,
                'placeholder': 'Email subject line...',
            }),
            'body': forms.Textarea(attrs={
                'id': 'step-body',
                'rows': 12,
                'class': INPUT_CSS,
            }),
            'video_file': forms.ClearableFileInput(attrs={
                'class': INPUT_CSS,
            }),
            'video': forms.Select(attrs={
                'class': INPUT_CSS,
            }),
        }
        labels = {
            'delay_days': 'Delay (days)',
            'delay_hours': 'Delay (hours)',
            'video_file': 'Video attachment',
            'video': 'Video from library',
        }

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['video'].required = False
        if team:
            from apps.videos.models import Video
            self.fields['video'].queryset = Video.objects.filter(
                team=team, status=Video.STATUS_READY,
            )
        else:
            self.fields['video'].queryset = self.fields['video'].queryset.none()
