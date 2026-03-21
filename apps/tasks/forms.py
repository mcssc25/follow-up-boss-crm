from django import forms

from apps.accounts.models import User
from apps.contacts.models import Contact
from apps.tasks.models import Task

INPUT_CLASS = (
    'mt-1 block w-full rounded-md border-gray-300 shadow-sm '
    'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
)


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'due_date', 'priority',
            'contact', 'assigned_to',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': INPUT_CLASS,
            }),
            'due_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': INPUT_CLASS,
            }),
            'priority': forms.Select(attrs={'class': INPUT_CLASS}),
            'contact': forms.Select(attrs={'class': INPUT_CLASS}),
            'assigned_to': forms.Select(attrs={'class': INPUT_CLASS}),
        }

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        if team:
            self.fields['assigned_to'].queryset = User.objects.filter(team=team)
            self.fields['contact'].queryset = Contact.objects.filter(team=team)
        else:
            self.fields['assigned_to'].queryset = User.objects.none()
            self.fields['contact'].queryset = Contact.objects.none()
        self.fields['contact'].required = False
        self.fields['contact'].empty_label = '-- No Contact --'
