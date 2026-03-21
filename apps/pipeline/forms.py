from django import forms

from apps.accounts.models import User
from apps.contacts.models import Contact
from apps.pipeline.models import Deal, PipelineStage

FIELD_CSS = 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = [
            'contact', 'title', 'stage', 'assigned_to',
            'value', 'expected_close_date',
        ]
        widgets = {
            'contact': forms.Select(attrs={'class': FIELD_CSS}),
            'title': forms.TextInput(attrs={
                'class': FIELD_CSS,
                'placeholder': 'Deal title',
            }),
            'stage': forms.Select(attrs={'class': FIELD_CSS}),
            'assigned_to': forms.Select(attrs={'class': FIELD_CSS}),
            'value': forms.NumberInput(attrs={
                'class': FIELD_CSS,
                'placeholder': '0.00',
                'step': '0.01',
            }),
            'expected_close_date': forms.DateInput(attrs={
                'class': FIELD_CSS,
                'type': 'date',
            }),
        }

    def __init__(self, *args, team=None, pipeline=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        self.pipeline = pipeline

        if team:
            self.fields['contact'].queryset = Contact.objects.filter(team=team)
            self.fields['assigned_to'].queryset = User.objects.filter(team=team)
        else:
            self.fields['contact'].queryset = Contact.objects.none()
            self.fields['assigned_to'].queryset = User.objects.none()

        if pipeline:
            self.fields['stage'].queryset = PipelineStage.objects.filter(pipeline=pipeline)
        elif self.instance and self.instance.pk:
            self.fields['stage'].queryset = PipelineStage.objects.filter(
                pipeline=self.instance.pipeline
            )
        else:
            self.fields['stage'].queryset = PipelineStage.objects.none()

        self.fields['assigned_to'].required = False
        self.fields['assigned_to'].empty_label = '-- Unassigned --'
        self.fields['value'].required = False
        self.fields['expected_close_date'].required = False

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.pipeline:
            instance.pipeline = self.pipeline
        if commit:
            instance.save()
        return instance
