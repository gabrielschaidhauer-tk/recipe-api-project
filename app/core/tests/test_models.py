"""
Tests for Models
"""

from unittest.mock import patch
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser

from core import models


def create_user(email="user@example.com", password="testpass123"):
    return get_user_model().objects.create_user(email, password)


class ModelTests(TestCase):
    """Test models."""

    def test_create_user_with_email_succesful(self):
        email = "test@example.com"
        password = "testpass123"
        user: AbstractBaseUser = get_user_model().objects.create_user(
            email=email, password=password
        )

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalized(self):
        """Test email is normalized for new users."""
        sample_emails = [
            ["test1@EXAMPLE.com", "test1@example.com"],
            ["Test2@Example.com", "Test2@example.com"],
            ["TEST3@EXAMPLE.COM", "TEST3@example.com"],
            ["test4@example.COM", "test4@example.com"],
        ]

        for email, expected in sample_emails:
            user = get_user_model().objects.create_user(email, "sample123")
            self.assertEqual(user.email, expected)

    def test_new_user_without_email_raises_error(self):
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user("", "test123")

    def test_create_super_user(self):
        user = get_user_model().objects.create_superuser(
            "test@example.com", "test123"
        )

        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_create_recipe(self):
        user = get_user_model().objects.create_superuser(
            "test@example.com", "test123"
        )

        recipe = models.Recipe.objects.create(
            user=user,
            title="Sample recipe name",
            time_minutes=5,
            price=Decimal("5.50"),
            description="Sample recipe description",
        )

        self.assertEqual(str(recipe), recipe.title)

    def test_create_ingredient(self):
        user = create_user()
        ingredient = models.Ingredient.objects.create(
            user=user, name="Cucumber"
        )

        self.assertEqual(str(ingredient), ingredient.name)

    @patch("core.models.uuid.uuid4")
    def test_recipe_file_name_uuid(self, mock_uuid):
        uuid = "test-uuid"
        mock_uuid.return_value = uuid
        file_path = models.recipe_image_file_path(None, "example.jpg")

        expected_path = f"uploads/recipe/{uuid}.jpg"
        self.assertEqual(file_path, expected_path)
