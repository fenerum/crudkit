from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from crudkit.models import ChangeLog
from crudkit_assistant import background
from crudkit_assistant.models import Agent


@receiver(post_save, sender=ChangeLog, dispatch_uid="crudkit_assistant_change_logged")
def _change_logged(sender, instance, created, **kwargs):
    if created:
        background.on_change_logged(instance)


@receiver(post_save, sender=Agent, dispatch_uid="crudkit_assistant_agent_saved")
@receiver(post_delete, sender=Agent, dispatch_uid="crudkit_assistant_agent_deleted")
def _agent_changed(sender, **kwargs):
    background.forget_record_agents()
