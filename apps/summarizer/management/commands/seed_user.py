from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from faker import Faker


class Command(BaseCommand):
    help = 'Seeds the database with dummy users.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of users to create (default: 10)'
        )

    def handle(self, *args, **options):
        count = options['count']
        User = get_user_model()
        fake = Faker('id_ID')

        self.stdout.write(f"Creating {count} dummy users...")

        created_count = 0
        for _ in range(count):
            try:
                first_name = fake.first_name()
                last_name = fake.last_name()
                username = f"{first_name.lower()}{fake.random_number(digits=3)}"
                email = f"{username}@example.com"

                if User.objects.filter(username=username).exists():
                    continue

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password='password123',
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True
                )

                self.stdout.write(self.style.SUCCESS(
                    f"Created user: {username}"))
                created_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Error creating user: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"Successfully created {created_count} users."))
