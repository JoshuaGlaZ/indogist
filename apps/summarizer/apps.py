import sys
from django.apps import AppConfig

class SummarizerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.summarizer'

    def ready(self):
        if 'runserver' or 'seed_summary' in sys.argv:
            from ml.ner.loader import load_all_models
            load_all_models()
