from django.core.mail import send_mail
from django.core.management.base import NoArgsCommand, CommandError

from mailer.models import Email

class Command(NoArgsCommand):
    help = 'Send emails to everyone in the database'

    def handle_noargs(self, **options):
        for email in Email.objects.filter(status=0):
            # from mail_templated import send_mail
	    # send_mail('email.tpl', {}, 'info@simply-scandinavian.co.uk',
	    #     [email.address])

            from mail_templated import EmailMessage
            from django.conf import settings

            msg = EmailMessage('email.tpl',
                {'email': email, 'site_prefix': settings.SITE_URL},
                to=[email.address])
            msg.from_email = 'info@simply-scandinavian.co.uk'
            msg.attach_alternative(msg.html, "text/html")
            msg.send()
            email.status = 1
            email.save()
            self.stdout.write(".", ending='')
