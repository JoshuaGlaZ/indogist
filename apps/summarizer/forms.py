from django import forms
from .models import Summary

class SummaryForm(forms.ModelForm):
    file = forms.FileField(required=False, label="Upload File (Optional)")
    
    compression_ratio = forms.FloatField(
        widget=forms.HiddenInput(), 
        initial=0.3,
        min_value=0.1,
        max_value=0.5
    )
    
    METHOD_CHOICES = [
        ('hybrid', 'Hybrid (AI/NER)'),
        ('traditional', 'Traditional (Statistical)'),
    ]
    method = forms.ChoiceField(
        choices=METHOD_CHOICES, 
        widget=forms.RadioSelect,
        initial='hybrid'
    )

    class Meta:
        model = Summary
        fields = ['title', 'original_text']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter document title'}),
            'original_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 8, 'placeholder': 'Paste text here...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = False
        self.fields['original_text'].required = False

    def clean(self):
        cleaned_data = super().clean()
        text = cleaned_data.get('original_text')
        file = cleaned_data.get('file')
        title = cleaned_data.get('title')

        if not file:
            if not text or not title:
                raise forms.ValidationError("Please provide both a Title and Original Text, or upload a template file.")


class SummaryFilterForm(forms.Form):
    """Form for filtering summaries in history page"""

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by title, text, or summary...',
            'id': 'search_input'
        })
    )

    method = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Methods'),
            ('hybrid', 'Hybrid (with NER)'),
            ('traditional', 'Traditional')
        ],
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'method_filter'
        })
    )

    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('-created_at', 'Newest First'),
            ('created_at', 'Oldest First'),
            ('title', 'Title (A-Z)'),
            ('-title', 'Title (Z-A)'),
            ('word_count_original', 'Original Length (Low-High)'),
            ('-word_count_original', 'Original Length (High-Low)'),
        ],
        initial='-created_at',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'sort_filter'
        })
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'id': 'date_from'
        }),
        label='From Date'
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'id': 'date_to'
        }),
        label='To Date'
    )


class ComparisonForm(forms.Form):
    """Form for comparing traditional vs hybrid methods"""

    title = forms.CharField(
        max_length=500,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter document title'
        })
    )

    text = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': 'Paste your Indonesian text here...'
        })
    )

    compression_ratio = forms.ChoiceField(
        choices=[
            ('0.2', 'Short (20%)'),
            ('0.3', 'Medium (30%)'),
            ('0.4', 'Long (40%)'),
            ('0.5', 'Extra Long (50%)'),
        ],
        initial='0.3',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )

    def clean_text(self):
        """Validate text length"""
        text = self.cleaned_data.get('text', '').strip()
        if len(text.split()) < 10:
            raise forms.ValidationError(
                'Text is too short for comparison. Please provide at least 10 words.'
            )
        return text

    def clean_compression_ratio(self):
        """Convert to float"""
        ratio = self.cleaned_data.get('compression_ratio')
        return float(ratio)
