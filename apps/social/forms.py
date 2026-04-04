from django import forms

from apps.campaigns.models import Campaign

from .models import KeywordTrigger


class KeywordTriggerForm(forms.ModelForm):
    class Meta:
        model = KeywordTrigger
        fields = [
            'keyword', 'match_type', 'platform', 'is_active',
            'reply_text', 'reply_link',
            'tags', 'campaign', 'create_contact', 'notify_agent',
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
            'reply_text': forms.Textarea(attrs={
                'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'rows': 4,
                'placeholder': 'The auto-reply message...',
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
