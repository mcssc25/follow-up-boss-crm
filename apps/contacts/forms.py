from django import forms

from apps.accounts.models import User
from apps.contacts.models import Contact


class ContactForm(forms.ModelForm):
    tags_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter tags separated by commas',
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        }),
        label='Tags',
        help_text='Separate multiple tags with commas.',
    )

    class Meta:
        model = Contact
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'address', 'source', 'assigned_to',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'address': forms.Textarea(attrs={
                'rows': 3,
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'source': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
            }),
        }

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        if team:
            self.fields['assigned_to'].queryset = User.objects.filter(team=team)
        else:
            self.fields['assigned_to'].queryset = User.objects.none()
        self.fields['assigned_to'].required = False
        self.fields['assigned_to'].empty_label = '-- Unassigned --'

        # Pre-populate tags_input from existing tags
        if self.instance and self.instance.pk and self.instance.tags:
            self.initial['tags_input'] = ', '.join(self.instance.tags)

    def clean_tags_input(self):
        raw = self.cleaned_data.get('tags_input', '')
        if not raw.strip():
            return []
        return [tag.strip() for tag in raw.split(',') if tag.strip()]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.tags = self.cleaned_data.get('tags_input', [])
        if self.team:
            instance.team = self.team
        if commit:
            instance.save()
        return instance


class ContactNoteForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Add a note...',
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        }),
        label='',
    )


class LogActivityForm(forms.Form):
    ACTIVITY_CHOICES = [
        ('call_logged', 'Call Logged'),
        ('email_sent', 'Email Sent'),
        ('note_added', 'Note Added'),
    ]

    activity_type = forms.ChoiceField(
        choices=ACTIVITY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        }),
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Describe the activity...',
            'class': 'block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
        }),
        required=False,
    )
