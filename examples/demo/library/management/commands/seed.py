import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from library.models import Author, Book

SAMPLE_BOOKS = {
    "Ursula K. Le Guin": [
        ("The Left Hand of Darkness", datetime.date(1969, 3, 1)),
        ("The Dispossessed", datetime.date(1974, 5, 1)),
    ],
    "Octavia E. Butler": [
        ("Kindred", datetime.date(1979, 6, 1)),
        ("Parable of the Sower", datetime.date(1993, 10, 4)),
    ],
    "Italo Calvino": [
        ("Invisible Cities", datetime.date(1972, 11, 3)),
        ("If on a winter's night a traveller", datetime.date(1979, 6, 1)),
    ],
}


class Command(BaseCommand):
    help = "Create the demo superuser (admin/admin) and sample library data. Idempotent."

    def handle(self, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@example.com", "is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password("admin")
            user.save()
            self.stdout.write(self.style.SUCCESS("Created superuser 'admin' (password: 'admin')."))

        audit = {"created_by": user, "updated_by": user}
        for author_name, books in SAMPLE_BOOKS.items():
            author, _ = Author.objects.get_or_create(name=author_name, defaults=audit)
            for title, published_date in books:
                Book.objects.get_or_create(
                    title=title,
                    author=author,
                    defaults={"published_date": published_date, **audit},
                )
        self.stdout.write(
            f"Database has {Author.objects.count()} authors and {Book.objects.count()} books."
        )
