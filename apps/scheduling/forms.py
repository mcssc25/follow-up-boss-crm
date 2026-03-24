from django import forms


class BookingForm(forms.Form):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone_number = forms.CharField(max_length=20)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))
