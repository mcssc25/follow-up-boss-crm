from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()

FORM_INPUT_CLASS = (
    'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm '
    'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
)


class StudentSignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = FORM_INPUT_CLASS

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'student'
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class CourseForm(forms.Form):
    title = forms.CharField(max_length=200)
    slug = forms.SlugField(max_length=100)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False)
    thumbnail = forms.ImageField(required=False)
    unlock_mode = forms.ChoiceField(choices=[
        ('time_drip', 'Time-based drip (weekly release)'),
        ('completion_based', 'Completion-based (unlock on finish)'),
    ])
    drip_interval_days = forms.IntegerField(initial=7, min_value=1, required=False)
    is_free = forms.BooleanField(required=False, initial=True)
    price = forms.DecimalField(max_digits=8, decimal_places=2, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.FileInput)):
                field.widget.attrs['class'] = FORM_INPUT_CLASS


class ModuleForm(forms.Form):
    title = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = FORM_INPUT_CLASS


class LessonForm(forms.Form):
    title = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False, help_text='Lesson notes (HTML allowed)')
    video_url = forms.URLField(required=False, help_text='YouTube or Vimeo URL')
    pdf_file = forms.FileField(required=False)
    duration_minutes = forms.IntegerField(required=False, min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = FORM_INPUT_CLASS


class AnnouncementForm(forms.Form):
    title = forms.CharField(max_length=200)
    body = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}))
    send_email = forms.BooleanField(required=False, label='Also send as email to enrolled students')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = FORM_INPUT_CLASS
