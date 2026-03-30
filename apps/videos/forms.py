from django import forms
from .models import Video

INPUT_CSS = (
    'mt-1 block w-full rounded-md border-gray-300 shadow-sm '
    'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
)


class VideoUploadForm(forms.ModelForm):
    storage_type = forms.ChoiceField(
        choices=Video.STORAGE_CHOICES,
        initial=Video.STORAGE_LOCAL,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Video
        fields = ['title', 'video_file', 'storage_type']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': INPUT_CSS,
                'placeholder': 'Give your video a name...',
            }),
            'video_file': forms.ClearableFileInput(attrs={
                'class': INPUT_CSS,
                'accept': 'video/*',
            }),
        }


class VideoEditForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = ['title']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': INPUT_CSS,
            }),
        }
