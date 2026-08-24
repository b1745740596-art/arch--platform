"""Account-security signals shared by API and Django admin password changes."""

from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import RememberToken


User = get_user_model()


@receiver(pre_save, sender=User, dispatch_uid='users_revoke_tokens_on_password_change')
def revoke_remember_tokens_on_password_change(sender, instance, **kwargs):
    """Invalidate persistent App login tokens whenever any code path changes a password."""
    if not instance.pk:
        return
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and 'password' not in update_fields:
        return
    previous = sender.objects.filter(pk=instance.pk).values_list('password', flat=True).first()
    if previous is not None and previous != instance.password:
        RememberToken.objects.filter(
            user_id=instance.pk,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
