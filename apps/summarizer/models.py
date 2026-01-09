from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class User(AbstractUser):
    pass


class Summary(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='summaries')
    title = models.CharField(max_length=500)
    original_text = models.TextField()
    summary_text = models.TextField()
    compression_ratio = models.DecimalField(max_digits=2, decimal_places=1,
        default=0.3, validators=[MinValueValidator(0.1), MaxValueValidator(0.5)])
    entities = models.JSONField(default=list, blank=True)
    method = models.CharField(max_length=20, choices=[('hybrid', 'Hybrid (with NER)'),
                 ('traditional', 'Traditional')], default='hybrid')

    created_at = models.DateTimeField(default=timezone.now)
    word_count_original = models.IntegerField(default=0)
    word_count_summary = models.IntegerField(default=0)

    added_to_dataset = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Summaries'

    def __str__(self):
        return f"{self.user.username} - {self.title[:50]}"

    def save(self, *args, **kwargs):
        self.word_count_original = len(self.original_text.split())
        self.word_count_summary = len(self.summary_text.split())
        super().save(*args, **kwargs)

    @property
    def actual_compression(self):
        if self.word_count_original > 0:
            return self.word_count_summary / self.word_count_original
        return 0

    def get_entities_by_type(self):
        entities_by_type = {}
        if isinstance(self.entities, list):
            for entity in self.entities:
                label = entity.get('label', 'UNKNOWN')
                text = entity.get('text', '')
                if label not in entities_by_type:
                    entities_by_type[label] = []
                if text not in entities_by_type[label]:
                    entities_by_type[label].append(text)
        return entities_by_type
