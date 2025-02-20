from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe, Ingredient

from recipe.serializers import RecipeSerializer, RecipeDetailSerializer
import tempfile
import os
from PIL import Image


RECIPES_URL = reverse("recipe:recipe-list")


def detail_url(recipe_id):
    return reverse("recipe:recipe-detail", args=[recipe_id])


def image_upload_url(recipe_id):
    return reverse("recipe:recipe-upload-image", args=[recipe_id])


def create_recipe(user, **params):
    """Create and return a sample recipe"""
    defaults = {
        "title": "Sample recipe",
        "time_minutes": 22,
        "price": Decimal("5.23"),
        "description": "Sample description",
        "link": "http://example.com/recipe.pdf",
    }

    defaults.update(params)

    recipe = Recipe.objects.create(user=user, **defaults)
    return recipe


class PublicRecipeAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        res = self.client.get(RECIPES_URL)
        self.assertEquals(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "user@example.com", "testpass123"
        )

        self.client.force_authenticate(self.user)

    def test_retrieve_recipes(self):
        create_recipe(user=self.user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)

        recipes = Recipe.objects.all().order_by("-id")
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_recipe_list_limited_to_user(self):
        other_user = get_user_model().objects.create_user(
            "other@examle.com", "testpass123"
        )

        create_recipe(user=other_user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_get_recipe_detail(self):
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(res.data, serializer.data)

    def test_create_recipe(self):
        payload = {
            "title": "Sample recipe",
            "time_minutes": 30,
            "price": Decimal("5.99"),
        }

        res = self.client.post(RECIPES_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=res.data["id"])

        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)

        self.assertEqual(recipe.user, self.user)

    def test_create_recipe_with_new_ingredients(self):
        payload = {
            "title": "Cauliflower Tacos",
            "time_minutes": 60,
            "price": Decimal("4.30"),
            "ingredients": [
                {"name": "Cauliflower"},
                {"name": "Salt"},
            ],
        }

        res = self.client.post(RECIPES_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)
        for ingredient in payload.get("ingredients"):
            exists = recipe.ingredients.filter(
                name=ingredient["name"]
            ).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_existing_ingredient(self):
        ingredient = Ingredient.objects.create(user=self.user, name="Lemon")

        payload = {
            "title": "Vietnamese Soup",
            "time_minutes": 25,
            "price": "2.55",
            "ingredients": [
                {"name": "Lemon"},
                {"name": "Fish Sauce"},
            ],
        }

        res = self.client.post(RECIPES_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)
        for ingredient in payload.get("ingredients"):
            exists = recipe.ingredients.filter(
                name=ingredient["name"]
            ).exists()
            self.assertTrue(exists)

    def test_create_ingredient_on_update(self):
        recipe = create_recipe(user=self.user)

        payload = {
            "ingredients": [
                {"name": "Limes"},
            ],
        }

        url = detail_url(recipe.id)

        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_ingredient = Ingredient.objects.get(user=self.user, name="Limes")
        self.assertIn(new_ingredient, recipe.ingredients.all())

    def test_update_recipe_assign_ingredient(self):
        ingredient1 = Ingredient.objects.create(user=self.user, name="Pepper")
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient1)

        ingredient2 = Ingredient.objects.create(user=self.user, name="Chili")
        payload = {"ingredients": [{"name": "Chili"}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(ingredient2, recipe.ingredients.all())
        self.assertNotIn(ingredient1, recipe.ingredients.all())

    def test_clear_recipe_ingredients(self):
        ingredient = Ingredient.objects.create(user=self.user, name="Garlic")
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient)

        payload = {"ingredients": []}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        recipe.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(), 0)

    def test_filter_by_ingredients(self):
        recipe1 = create_recipe(user=self.user, title="Pasta")
        recipe2 = create_recipe(user=self.user, title="Curry")
        recipe3 = create_recipe(user=self.user, title="Soup")

        ingredient1 = Ingredient.objects.create(user=self.user, name="Tomato")
        ingredient2 = Ingredient.objects.create(user=self.user, name="Ginger")

        recipe1.ingredients.add(ingredient1)
        recipe2.ingredients.add(ingredient2)

        serialized1 = RecipeSerializer(recipe1)
        serialized2 = RecipeSerializer(recipe2)
        serialized3 = RecipeSerializer(recipe3)

        params = {"ingredients": f"{ingredient1.id},{ingredient2.id}"}

        res = self.client.get(RECIPES_URL, params)

        self.assertIn(serialized1.data, res.data)
        self.assertIn(serialized2.data, res.data)
        self.assertNotIn(serialized3.data, res.data)


class ImageUploadTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="user@example.com", password="testpass123"
        )
        self.client.force_authenticate(self.user)
        self.recipe = create_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()

    def test_upload_image(self):
        url = image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as image_file:
            img = Image.new("RGB", (10, 10))
            img.save(image_file, format="JPEG")
            image_file.seek(0)
            payload = {"image": image_file}
            res = self.client.post(url, payload, format="multipart")

        self.recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("image", res.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bad_request(self):
        url = image_upload_url(self.recipe.id)

        payload = {"image": "notimage"}
        res = self.client.post(url, payload, format="multipart")

        self.recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
