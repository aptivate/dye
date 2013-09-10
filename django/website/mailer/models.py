from django.db import models

# Create your models here.
class Email(models.Model):
    address = models.CharField(max_length=128)

    STATUSES = (
        (0, 'Uncontacted'),
        (1, 'Email sent'),
        (2, 'Email refused'),
        (3, 'Email bounced'),
        (4, 'Unsubscribed'),
    )
    status = models.IntegerField(choices=STATUSES)
