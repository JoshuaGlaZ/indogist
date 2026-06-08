from django import forms
from django.utils.translation import gettext_lazy as _lazy
from .models import Summary


class SummaryForm(forms.ModelForm):
    file = forms.FileField(required=False, label=_lazy("Upload File (Optional)"))

    compression_ratio = forms.FloatField(
        widget=forms.HiddenInput(), initial=0.3, min_value=0.1, max_value=0.5
    )

    METHOD_CHOICES = [
        ("hybrid", _lazy("Hybrid (AI/NER)")),
        ("traditional", _lazy("Traditional (Statistical)")),
    ]
    method = forms.ChoiceField(
        choices=METHOD_CHOICES, widget=forms.RadioSelect, initial="hybrid"
    )

    class Meta:
        model = Summary
        fields = ["title", "original_text"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Enter document title"),
                }
            ),
            "original_text": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 8,
                    "placeholder": _("Paste text here..."),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = False
        self.fields["original_text"].required = False

    def clean(self):
        cleaned_data = super().clean()
        text = cleaned_data.get("original_text", "").strip()
        title = cleaned_data.get("title", "").strip()
        file = self.files.get("file")
        has_file = file is not None

        if not has_file:
            if not text:
                self.add_error(
                    "original_text", _lazy("Please provide text or upload a file.")
                )
            if not title:
                self.add_error(
                    "title", _lazy("Please provide a title or upload a file.")
                )
        return cleaned_data


class SummaryFilterForm(forms.Form):
    """Form for filtering summaries in history page"""

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Search by title, text, or summary..."),
                "id": "search_input",
            }
        ),
    )

    method = forms.ChoiceField(
        required=False,
        choices=[
            ("", _lazy("All Methods")),
            ("hybrid", _lazy("Hybrid (with NER)")),
            ("traditional", _lazy("Traditional")),
        ],
        widget=forms.Select(attrs={"class": "form-select", "id": "method_filter"}),
    )

    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ("-created_at", _lazy("Newest First")),
            ("created_at", _lazy("Oldest First")),
            ("title", _lazy("Title (A-Z)")),
            ("-title", _lazy("Title (Z-A)")),
            ("word_count_original", _lazy("Original Length (Low-High)")),
            ("-word_count_original", _lazy("Original Length (High-Low)")),
        ],
        initial="-created_at",
        widget=forms.Select(attrs={"class": "form-select", "id": "sort_filter"}),
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date", "id": "date_from"}
        ),
        label=_lazy("From Date"),
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date", "id": "date_to"}
        ),
        label=_lazy("To Date"),
    )


class ComparisonForm(forms.Form):
    """Form for comparing traditional vs hybrid methods"""

    title = forms.CharField(
        max_length=500,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": _("Enter document title"),
            }
        ),
    )

    text = forms.CharField(
        required=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 10,
                "placeholder": _("Paste your Indonesian text here..."),
            }
        ),
    )

    compression_ratio = forms.ChoiceField(
        choices=[
            ("0.2", _lazy("Short (20%)")),
            ("0.3", _lazy("Medium (30%)")),
            ("0.4", _lazy("Long (40%)")),
            ("0.5", _lazy("Extra Long (50%)")),
        ],
        initial="0.3",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def clean_text(self):
        """Validate text length"""
        text = self.cleaned_data.get("text", "").strip()
        if len(text.split()) < 10:
            raise forms.ValidationError(
                _lazy(
                    "Text is too short for comparison. Please provide at least 10 words."
                )
            )
        return text

    def clean_compression_ratio(self):
        """Convert to float"""
        ratio = self.cleaned_data.get("compression_ratio")
        return float(ratio)
