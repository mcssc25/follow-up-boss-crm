from django import forms

from apps.accounts.models import User
from apps.contacts.models import Contact, SmartList
from apps.pipeline.models import PipelineStage


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


INPUT_CLASS = (
    'mt-1 block w-full rounded-md border-gray-300 shadow-sm '
    'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
)


class SmartListForm(forms.ModelForm):
    """Form for creating/editing a SmartList.

    Each filter field is optional. Only non-empty fields are stored in the
    JSON ``filters`` column.
    """

    source = forms.ChoiceField(
        required=False,
        choices=[('', '-- Any --')] + Contact.SOURCE_CHOICES,
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
    )
    assigned_to = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.none(),
        empty_label='-- Any --',
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
    )
    tags_contain = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'e.g. buyer',
        }),
        label='Tags contain',
    )
    last_contacted_days_ago_gt = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'e.g. 30',
        }),
        label='Not contacted in (days)',
    )
    created_days_ago_lt = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'e.g. 7',
        }),
        label='Created within (days)',
    )
    has_deal_in_stage = forms.ModelChoiceField(
        required=False,
        queryset=PipelineStage.objects.none(),
        empty_label='-- Any --',
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
        label='Has deal in stage',
    )
    no_deal = forms.BooleanField(
        required=False,
        label='Has no deal',
    )

    class Meta:
        model = SmartList
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS}),
        }

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        if team:
            self.fields['assigned_to'].queryset = User.objects.filter(team=team)
            self.fields['has_deal_in_stage'].queryset = PipelineStage.objects.filter(
                pipeline__team=team,
            )

        # Pre-populate filter fields from existing filters JSON
        if self.instance and self.instance.pk and self.instance.filters:
            f = self.instance.filters
            for key in (
                'source', 'tags_contain', 'last_contacted_days_ago_gt',
                'created_days_ago_lt', 'no_deal',
            ):
                if key in f:
                    self.initial[key] = f[key]
            if 'assigned_to' in f:
                self.initial['assigned_to'] = f['assigned_to']
            if 'has_deal_in_stage' in f:
                self.initial['has_deal_in_stage'] = f['has_deal_in_stage']

    def build_filters(self):
        """Return a dict of only the non-empty filter values."""
        data = self.cleaned_data
        filters = {}

        if data.get('source'):
            filters['source'] = data['source']
        if data.get('assigned_to'):
            filters['assigned_to'] = data['assigned_to'].pk
        if data.get('tags_contain'):
            filters['tags_contain'] = data['tags_contain']
        if data.get('last_contacted_days_ago_gt'):
            filters['last_contacted_days_ago_gt'] = data['last_contacted_days_ago_gt']
        if data.get('created_days_ago_lt'):
            filters['created_days_ago_lt'] = data['created_days_ago_lt']
        if data.get('has_deal_in_stage'):
            filters['has_deal_in_stage'] = data['has_deal_in_stage'].pk
        if data.get('no_deal'):
            filters['no_deal'] = True

        return filters
