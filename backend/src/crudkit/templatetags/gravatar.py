import hashlib
from urllib.parse import urlencode

from django import template
from django.conf import settings

register = template.Library()


# return only the URL of the gravatar
# TEMPLATE USE:  {{ email|gravatar_url:150 }}
@register.filter
def gravatar_url(email, size=40):
    if not email:
        email = getattr(settings, "CRUDKIT_GRAVATAR_FALLBACK_EMAIL", None)
    params = {"s": str(size)}
    if not email:
        # No email and no configured fallback: gravatar's generic "mystery person"
        email = ""
        params["d"] = "mp"
    return "https://www.gravatar.com/avatar/%s?%s" % (
        hashlib.md5(email.lower().encode("utf-8").lower()).hexdigest(),
        urlencode(params),
    )
