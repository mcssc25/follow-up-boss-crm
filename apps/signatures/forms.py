from django import forms
from apps.signatures.models import Document

INPUT_CLASS = 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'


class DocumentCreateForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'email_message', 'expires_at']
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Document title'}),
            'email_message': forms.Textarea(attrs={
                'class': INPUT_CLASS,
                'rows': 4,
                'placeholder': 'Add a note to the signer',
            }),
            'expires_at': forms.DateTimeInput(attrs={'class': INPUT_CLASS, 'type': 'datetime-local'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        # pdf_files validation is handled in the view since Django widgets
        # don't support multiple file upload natively
        return cleaned_data
