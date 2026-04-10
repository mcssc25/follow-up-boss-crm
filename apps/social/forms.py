from django import forms

from apps.campaigns.models import Campaign

from .models import KeywordTrigger


class KeywordTriggerForm(forms.ModelForm):
    tags_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            'placeholder': 'e.g. condos, interested, phoenix',
        }),
        help_text='Comma-separated tags to apply to the contact',
    )

    class Meta:
        model = KeywordTrigger
        fields = [
            'keyword', 'match_type', 'platform', 'trigger_event', 'is_active',
            'reply_text', 'response_type', 'reply_link',
            'campaign', 'create_contact', 'notify_agent',
        ]
        widgets = {
            'keyword': forms.TextInput(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'placeholder': 'e.g. Condos',
            }),
            'match_type': forms.Select(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'platform': forms.Select(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'trigger_event': forms.Select(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'reply_text': forms.Textarea(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'rows': 4,
                'placeholder': 'The auto-reply message...',
            }),
            'response_type': forms.Select(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'reply_link': forms.URLInput(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'placeholder': 'https://example.com/guide.pdf',
            }),
        }

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        if team:
            self.fields['campaign'].queryset = Campaign.objects.filter(
                team=team, is_active=True,
            )
        self.fields['campaign'].required = False
        self.fields['campaign'].empty_label = '— No campaign —'

        # Pre-populate tags_input from existing tags JSON
        if self.instance and self.instance.pk and self.instance.tags:
            self.fields['tags_input'].initial = ', '.join(self.instance.tags)

    def clean_tags_input(self):
        raw = self.cleaned_data.get('tags_input', '')
        if not raw.strip():
            return []
        return [tag.strip() for tag in raw.split(',') if tag.strip()]

    def save(self, commit=True):
        self.instance.tags = self.cleaned_data['tags_input']
        return super().save(commit=commit)
