# Create your views here.

from django.http import HttpResponse
import datetime

from models import Email

def unsubscribe(request, address):
    email = Email.objects.get(address=address)
    email.status = 4
    email.save()
    html = "<html><body>Thanks, your email address %s has been removed from our list.</body></html>" % address
    return HttpResponse(html)
