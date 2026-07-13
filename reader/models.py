from django.db import models
from django.utils.text import slugify
from urllib.parse import urlparse

class Post(models.Model):
    title = models.CharField(max_length=255)
    url = models.URLField(unique=True, max_length=500)
    published_at = models.DateTimeField()
    summary = models.TextField(blank=True)
    content = models.TextField(blank=True)
    slug = models.SlugField(unique=True, max_length=255, blank=True)

    class Meta:
        ordering = ['-published_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            # Tenta extrair o slug da URL original do blog se possível, ou usa o título
            path_parts = urlparse(self.url).path.strip('/').split('/')
            if path_parts and path_parts[-1]:
                potential_slug = path_parts[-1].replace('.html', '')
                self.slug = slugify(potential_slug)
            else:
                self.slug = slugify(self.title)
            
            # Garante unicidade caso o slug já exista
            original_slug = self.slug
            count = 1
            while Post.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{count}"
                count += 1
                
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('reader:post_detail', kwargs={
            'year': self.published_at.year,
            'month': f"{self.published_at.month:02d}",
            'day': f"{self.published_at.day:02d}",
            'slug': self.slug
        })

    def __str__(self):
        return self.title

class ReadingProgress(models.Model):
    STATUS_CHOICES = [
        ('unread', 'Não Lido'),
        ('reading', 'Lendo'),
        ('read', 'Lido'),
    ]
    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name='progress')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unread')
    scroll_position = models.FloatField(default=0.0)  # Em porcentagem (0 a 100)
    last_read_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.post.title} - {self.get_status_display()} ({self.scroll_position:.1f}%)"


class YouTubeVideo(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='videos')
    youtube_id = models.CharField(max_length=50)
    title = models.CharField(max_length=255, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    url = models.URLField(max_length=500)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.title or self.youtube_id} ({self.post.title})"

