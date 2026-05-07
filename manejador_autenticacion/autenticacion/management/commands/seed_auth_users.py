"""
Seeds two test users for local JWT mode (docker compose without AWS).
empresa_a@bite.co  → empresa_id 550e8400-e29b-41d4-a716-446655440001 (matches JMeter payload)
empresa_b@bite.co  → empresa_id 550e8400-e29b-41d4-a716-446655440002

In Cognito (production), users must be created via terraform or the AWS console.
Password: BiteCo2024!
"""
from django.core.management.base import BaseCommand
from autenticacion.models import UsuarioLocal

SEED_USERS = [
    {
        'email': 'empresa_a@bite.co',
        'password': 'BiteCo2024!',
        'empresa_id': '550e8400-e29b-41d4-a716-446655440001',
    },
    {
        'email': 'empresa_b@bite.co',
        'password': 'BiteCo2024!',
        'empresa_id': '550e8400-e29b-41d4-a716-446655440002',
    },
]


class Command(BaseCommand):
    help = 'Seed test users for local JWT auth mode'

    def handle(self, *args, **options):
        for data in SEED_USERS:
            user, created = UsuarioLocal.objects.get_or_create(
                email=data['email'],
                defaults={'empresa_id': data['empresa_id']},
            )
            if created or not user.password_hash:
                user.empresa_id = data['empresa_id']
                user.set_password(data['password'])
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created user: {data['email']}"))
            else:
                self.stdout.write(f"User already exists: {data['email']}")
