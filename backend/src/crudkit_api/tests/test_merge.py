from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from crudkit.models import ChangeLog, ExternalObject, FeedItem, WorkLog
from tests.testapp.models import Customer, Reminder, Ticket, Topic


class MergeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="admin", password="pw")
        self.audit = {"created_by": self.user, "updated_by": self.user}
        self.a, self.b, self.c = (
            Customer.objects.create(name=name, email=f"{name}@example.com", **self.audit) for name in ("a", "b", "c")
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def merge(self, kept, *merged):
        return self.client.post(
            f"/api/v1/{kept.TYPE_ID}/{kept.pk}/merge/",
            {"merge": [kept.pk, *(obj.pk for obj in merged)], "id": kept.pk},
            format="json",
        )

    def test_selected_id_survives_regardless_of_url_pk(self):
        response = self.client.post(
            f"/api/v1/CUS/{self.a.pk}/merge/",
            {"merge": [self.a.pk, self.b.pk, self.c.pk], "id": self.b.pk, "name": self.a.pk, "email": self.c.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["redirect"], self.b.pk)
        for obj in (self.a, self.b, self.c):
            obj.refresh_from_db()
        self.assertFalse(self.b.deleted)
        self.assertEqual((self.b.name, self.b.email), ("a", "c@example.com"))
        for merged in (self.a, self.c):
            self.assertTrue(merged.deleted)
            self.assertEqual(merged.merged_into_id, self.b.pk)

    def test_foreign_keys_move_whatever_their_on_delete(self):
        kept, merged = (Topic.objects.create(name=name, **self.audit) for name in ("Billing", "Invoices"))
        Customer.objects.filter(pk=self.a.pk).update(topic=merged)  # SET_NULL
        ticket = Ticket.objects.create(subject="Help", customer=self.a, topic=merged, **self.audit)
        ticket.soft_delete()

        response = self.merge(kept, merged)

        self.assertEqual(response.status_code, 200, response.data)
        self.a.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(self.a.topic, kept)
        self.assertEqual(ticket.topic, kept)

    def test_cascading_children_move_instead_of_blocking(self):
        ticket = Ticket.objects.create(subject="Help", customer=self.a, **self.audit)

        response = self.merge(self.b, self.a)

        self.assertEqual(response.status_code, 200, response.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.customer, self.b)

    def test_generic_foreign_keys_move_but_the_change_log_stays(self):
        content_type = ContentType.objects.get_for_model(Customer)
        generic = {"related_content_type": content_type, "related_object_id": self.a.pk}
        feed_item = FeedItem.objects.create(parent_object=self.a, body="Called them", **self.audit)
        external = ExternalObject.objects.create(
            system_name="hubspot", system_id="1", related_object=self.a, **self.audit
        )
        reminder = Reminder.objects.create(**generic, **self.audit)
        work_log = WorkLog.objects.create(**generic, **self.audit)
        change_log = ChangeLog.objects.create(**generic, label="Renamed", **self.audit)

        response = self.merge(self.b, self.a)

        self.assertEqual(response.status_code, 200, response.data)
        for row in (feed_item, external, reminder, work_log, change_log):
            row.refresh_from_db()
        self.assertEqual(feed_item.parent_object, self.b)
        self.assertEqual(external.related_object, self.b)
        self.assertEqual(reminder.target, self.b)
        self.assertEqual(work_log.related_object, self.b)
        self.assertEqual(change_log.related_object, self.a)

    def test_rows_left_behind_fail_the_merge(self):
        ticket = Ticket.objects.create(subject="Help", **self.audit)
        ticket.watchers.add(self.a)

        response = self.merge(self.b, self.a)

        self.assertEqual(response.status_code, 400)
        self.assertIn("watchers", response.data["errors"][0])
        self.a.refresh_from_db()
        self.assertFalse(self.a.deleted)
        self.assertEqual(list(ticket.watchers.all()), [self.a])
