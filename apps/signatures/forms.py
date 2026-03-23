from django import forms
from apps.signatures.models import Document

INPUT_CLASS = 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'


class DocumentCreateForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'pdf_file', 'expires_at']
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Document title'}),
            'pdf_file': forms.FileInput(attrs={'class': INPUT_CLASS, 'accept': '.pdf'}),
            'expires_at': forms.DateTimeInput(attrs={'class': INPUT_CLASS, 'type': 'datetime-local'}),
        }

    def clean_pdf_file(self):
        f = self.cleaned_data.get('pdf_file')
        if f and not f.name.lower().endswith('.pdf'):
            raise forms.ValidationError('Only PDF files are allowed.')
        if f and f.size > 50 * 1024 * 1024:
            raise forms.ValidationError('File size must be under 50MB.')
        return f
