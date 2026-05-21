# Create your models here.
from django.db import models

class Feature(models.Model):
    names = models.CharField(max_length=100)
    colors = models.CharField(max_length=500)