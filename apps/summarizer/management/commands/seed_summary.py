from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.conf import settings
from apps.summarizer.models import Summary
from ml.summarization.hybrid import predict_and_summarize
from ml.summarization.traditional import summarize_traditional
from ml.ner.loader import load_all_models
import json
import os
import glob
import secrets
from faker import Faker
from django.utils import timezone 

# Fallback texts just in case no files are found
SAMPLE_TEXTS = [
    {
        "title": "Pertumbuhan Ekonomi Indonesia 2024",
        "text": """Perekonomian Indonesia pada tahun 2024 diperkirakan akan tetap tumbuh positif di tengah ketidakpastian global. Bank Indonesia memproyeksikan pertumbuhan ekonomi berada pada kisaran 4,7% hingga 5,5%. Pertumbuhan ini didorong oleh konsumsi rumah tangga yang kuat serta investasi yang terus meningkat, terutama di sektor infrastruktur dan hilirisasi industri. Selain itu, ekspor komoditas unggulan seperti nikel dan batu bara masih menjadi penopang utama, meskipun harga komoditas global cenderung melandai. Pemerintah juga terus berupaya menjaga stabilitas inflasi dan nilai tukar rupiah untuk mendukung daya beli masyarakat."""
    },
    {
        "title": "Perkembangan Kecerdasan Buatan",
        "text": """Kecerdasan Buatan (AI) semakin mendominasi berbagai sektor kehidupan manusia. Mulai dari asisten virtual di ponsel pintar hingga sistem otonom pada kendaraan, AI telah mengubah cara kita bekerja dan berinteraksi. Di Indonesia, adopsi AI mulai terlihat di sektor perbankan, kesehatan, e-commerce, dan layanan pelanggan. Meskipun membawa banyak manfaat efisiensi, perkembangan AI juga memunculkan kekhawatiran terkait privasi data dan potensi penggantian tenaga kerja manusia."""
    }
]

class Command(BaseCommand):
    help = 'Seeds the database with dummy summaries using IndoSum Dataset files.'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='The username to assign summaries to')
        parser.add_argument('--count', type=int, default=20, help='Number of summaries to create (default: 20)')

    def load_dataset_samples(self, target_count):
        """Scans the data/indosum directory for .jsonl files and loads random samples."""
        dataset_dir = os.path.join(settings.BASE_DIR, 'data', 'indosum')
        loaded_data = []
        
        if not os.path.exists(dataset_dir):
            self.stdout.write(self.style.WARNING(f"Dataset directory not found at: {dataset_dir}"))
            return []

        files = glob.glob(os.path.join(dataset_dir, '*.jsonl'))
        
        if not files:
            self.stdout.write(self.style.WARNING(f"No .jsonl files found in {dataset_dir}"))
            return []

        self.stdout.write(f"Found {len(files)} dataset files. Reading samples...")
        
        secure_random = secrets.SystemRandom()
        secure_random.shuffle(files)

        for file_path in files:
            if len(loaded_data) >= target_count * 3: 
                break
                
            filename = os.path.basename(file_path)
            self.stdout.write(f"  - Reading from {filename}...")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    secure_random.shuffle(lines)
                    
                    for line in lines:
                        if len(loaded_data) >= target_count * 3: 
                            break
                        
                        try:
                            data = json.loads(line)
                            
                            title = data.get('title', '')
                            if not title and 'id' in data:
                                title = data['id'].split('-')[1:] 
                                title = " ".join(title).title()

                            text = ""
                            if 'paragraphs' in data:
                                paragraph_texts = []
                                for paragraph in data['paragraphs']:
                                    sentence_texts = []
                                    for sentence in paragraph:
                                        valid_tokens = [t for t in sentence if t and t.strip()]
                                        if valid_tokens:
                                            sent_str = " ".join(valid_tokens)
                                            sentence_texts.append(sent_str)
                                    if sentence_texts:
                                        para_str = " ".join(sentence_texts)
                                        paragraph_texts.append(para_str)
                                if paragraph_texts:
                                    text = "\n\n".join(paragraph_texts)

                            elif 'text' in data:
                                text = data['text']
                            elif 'article' in data:
                                text = data['article']

                            if text and len(text) > 300 and title: 
                                loaded_data.append({'title': title, 'text': text})
                                
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error reading {filename}: {e}"))

        return loaded_data

    def handle(self, *args, **options):
        # Explicitly load the models before starting
        self.stdout.write("Initializing AI Models... (This may take a moment)")
        load_all_models()
        self.stdout.write("Models Loaded Successfully.")

        username = options['username']
        count = options['count']
        User = get_user_model()

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        source_data = self.load_dataset_samples(count)

        if not source_data:
            self.stdout.write(self.style.WARNING("Could not load enough data. Using fallback texts."))
            source_data = SAMPLE_TEXTS
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully loaded {len(source_data)} candidate articles."))

        self.stdout.write(f"Generating {count} summaries for user: {user.username}...")

        fake = Faker('id_ID')
        secure_random = secrets.SystemRandom()

        success_count = 0
        attempts = 0
        max_attempts = count * 2 

        while success_count < count and attempts < max_attempts:
            attempts += 1
            
            base_data = secure_random.choice(source_data)
            title = base_data['title']
            original_text = base_data['text']
            
            compression_ratio = secure_random.choice([0.2, 0.3, 0.4, 0.5])
            method_options = ['hybrid', 'hybrid', 'hybrid', 'traditional']
            method = secure_random.choice(method_options)

            self.stdout.write(f"  [{success_count+1}/{count}] Processing: {title[:30]}... ({method})")

            try:
                if method == 'hybrid':
                    result = predict_and_summarize(
                        text=original_text,
                        title=title,
                        compression_ratio=compression_ratio
                    )
                    summary_text = result['summary']
                    entities = result['entities']
                else:
                    summary_text = summarize_traditional(
                        text=original_text,
                        title=title,
                        compression_ratio=compression_ratio
                    )
                    entities = []
                
                if not summary_text:
                     self.stdout.write(self.style.WARNING(f"   Skipped: Empty summary generated."))
                     continue

                # Generate a timezone-aware datetime properly
                # We use Django's timezone.now() to get the current timezone context
                current_tz = timezone.get_current_timezone()
                created_dt = fake.date_time_between(
                    start_date='-60d', 
                    end_date='now', 
                    tzinfo=current_tz
                )

                Summary.objects.create(
                    user=user,
                    title=title,
                    original_text=original_text,
                    summary_text=summary_text,
                    compression_ratio=compression_ratio,
                    entities=entities,
                    method=method,
                    created_at=created_dt
                )
                success_count += 1
                
            except Exception as e:
                if "'NoneType' object has no attribute 'stem'" in str(e):
                     self.stdout.write(self.style.WARNING(f"   Skipped (NER/Stem Error): Malformed text input."))
                else:
                     self.stdout.write(self.style.ERROR(f"   Failed to process: {e}"))

        if success_count < count:
             self.stdout.write(self.style.WARNING(f'Finished with partial success. Created {success_count}/{count} summaries.'))
        else:
             self.stdout.write(self.style.SUCCESS(f'Done! Created {count} summaries for {username}.'))