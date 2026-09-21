import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from crudkit.models import Layout, View
from library.models import Author, Book, Reading

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

# (name, book title, status, priority, pages, rating)
SAMPLE_READINGS = [
    ("Book club: Kindred", "Kindred", "finished", "high", 264, 5),
    ("Reread Earthsea prequel", "The Left Hand of Darkness", "reading", "low", 304, 4),
    ("Anarchist utopia", "The Dispossessed", "to_read", "high", 387, 3),
    ("Sower for school", "Parable of the Sower", "reading", "high", 345, 5),
    ("Cities on the train", "Invisible Cities", "finished", "low", 165, 4),
    ("Traveller, again", "If on a winter's night a traveller", "to_read", "low", 260, 2),
    ("Kindred audiobook", "Kindred", "to_read", "low", 264, 3),
    ("Dispossessed notes", "The Dispossessed", "finished", "high", 387, 5),
    ("Darkness with friends", "The Left Hand of Darkness", "to_read", "high", 304, 4),
    ("Calvino in Italian", "Invisible Cities", "reading", "low", 165, 3),
    ("Sower sequel prep", "Parable of the Sower", "to_read", "low", 345, 2),
    ("Winter traveller club", "If on a winter's night a traveller", "finished", "high", 260, 4),
]

# One view per layout. The default list view keeps /RDG a plain list.
SAMPLE_VIEWS = {
    "All readings": {"layout": "list", "default": True, "fields": ["name", "status", "priority"]},
    "Board": {"layout": "kanban", "fields": ["name", "priority"], "group_by": "status"},
    "Covers": {"layout": "gallery", "fields": ["name", "status"]},
    "Pages vs rating": {"layout": "quadrant", "fields": ["pages", "rating", "name"]},
    "Lanes": {
        "layout": "swimlane",
        "fields": ["name"],
        "group_by": "status",
        "pivot_by": "priority",
    },
}


class Command(BaseCommand):
    help = (
        "Create the demo superuser (admin/admin), sample library data, saved views "
        "and an Author layout. Idempotent."
    )

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

        for name, title, status, priority, pages, rating in SAMPLE_READINGS:
            Reading.objects.get_or_create(
                name=name,
                defaults={
                    "book": Book.objects.get(title=title),
                    "status": status,
                    "priority": priority,
                    "pages": pages,
                    "rating": rating,
                    **audit,
                },
            )

        for name, config in SAMPLE_VIEWS.items():
            View.objects.get_or_create(
                model="RDG", name=name, defaults={"public": True, **config, **audit}
            )

        # Another user's private view: must stay hidden from admin's menus and view tabs.
        reader, _ = User.objects.get_or_create(username="reader")
        View.objects.get_or_create(
            model="RDG",
            name="Reader's private picks",
            defaults={"public": False, "fields": ["name"], "created_by": reader, "updated_by": reader},
        )

        Layout.objects.get_or_create(
            model="AUT",
            defaults={"inlines": [["BOK", ["title", "published_date"]], ["FEI", []]], **audit},
        )

        self.stdout.write(
            f"Database has {Author.objects.count()} authors, {Book.objects.count()} books "
            f"and {Reading.objects.count()} readings."
        )
