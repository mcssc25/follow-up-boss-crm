from django import forms


class BookingForm(forms.Form):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone_number = forms.CharField(max_length=20)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))


from .models import EventType
from apps.accounts.models import User
from apps.contacts.models import Tag


class EventTypeForm(forms.ModelForm):
    class Meta:
        model = EventType
        fields = [
            'name', 'slug', 'description', 'duration_minutes',
            'location_type', 'color', 'is_active', 'min_advance_hours',
            'buffer_minutes', 'timezone',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    owner = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=True,
        label='Assigned To',
    )

    tag_ids = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        if team:
            self.fields['tag_ids'].queryset = Tag.objects.filter(team=team)
            self.fields['owner'].queryset = User.objects.filter(team=team)
